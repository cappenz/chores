from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from speech_agent.audio import (
    CHUNK_SIZE,
    CHANNELS,
    RECEIVE_SAMPLE_RATE,
    SEND_SAMPLE_RATE,
    _input_device_info,
    _output_device_info,
    pcm_rms_int16,
)
from speech_agent.tools import SpeechChoresApi, build_tools, handle_tool_call

MIC_MIME = "audio/pcm;rate=16000"
MODELS = (
    "gemini-3.1-flash-live-preview",
    "gemini-2.5-flash-native-audio-preview-12-2025",
)
STOP_LISTENING_PHRASES = ("goodbye", "stop listening")
VOICE_NAME = "Schedar"
GEMINI_SESSION_CLOSE_TIMEOUT_SECONDS = 2.0
ConnectionCallback = Callable[[bool], Awaitable[None] | None]
TextCallback = Callable[[str], Awaitable[None] | None]
INITIAL_GREETING_PROMPT = "Greet the family now. Say only: Hello!"
SYSTEM_INSTRUCTION = """
You are the helpful kitchen voice assistant for the Appenzeller family.

## About the family

Family members are:
- Guido, 54, Venture Capitalist, loves technology, peanuts and flying planes
- Isabelle, 25, Quantitative Marketing and is really good looking
- Daniel, 18, goes to Crystal Springs School, will go to college in the fall
- Charlotte, 16, goes to Nueva School,loves horses
- Thomas, 12, will soon go to Khan Lab School, plays soccer,loves bugs
- Zach (the rabbit), loves carrots

They live in Menlo Park, California. 

## About your personality

Your name is Jarvis. You are friendly, funny, intelligent and high energy.
You hate racoons and cloudy weather. 

Don't over-use the facts above, use then only when there is a relevant conversation topic.
Answer questions only. Don't offer additional information or suggestions.

Now start the conversation with one of these greetings:
- Hello!
- Hi there!
- Hello Appenzellers!

"""


class ListeningComplete(Exception):
    """Raised when the speech agent should return to wake-word mode."""


class AudioLoop:
    def __init__(
        self,
        session,
        chores: SpeechChoresApi,
        *,
        debug: bool,
        input_device_index: int | None,
        output_device_index: int | None,
        idle_timeout_seconds: float,
        on_assistant_speaking: ConnectionCallback | None = None,
        on_assistant_response_text: TextCallback | None = None,
    ) -> None:
        self.session = session
        self.chores = chores
        self.debug = debug
        self.input_device_index = input_device_index
        self.output_device_index = output_device_index
        self.idle_timeout_seconds = idle_timeout_seconds
        self.audio_in_queue: asyncio.Queue[bytes] | None = None
        self.out_queue: asyncio.Queue[dict] | None = None
        self.audio_stream = None
        self.pyaudio = _pyaudio()
        self.pya = self.pyaudio.PyAudio()
        self._send_chunks = 0
        self._last_user_activity = time.monotonic()
        self.stop_reason = "listening session ended"
        self._mic_send_silence = False
        self._mic_reopen_task: asyncio.Task | None = None
        self.on_assistant_speaking = on_assistant_speaking
        self.on_assistant_response_text = on_assistant_response_text
        self._assistant_speaking = False

    async def run(self) -> None:
        self.audio_in_queue = asyncio.Queue()
        self.out_queue = asyncio.Queue(maxsize=5)
        tasks: list[asyncio.Task] = []
        try:
            tasks = [
                asyncio.create_task(self.send_realtime()),
                asyncio.create_task(self.listen_audio()),
                asyncio.create_task(self.receive_audio()),
                asyncio.create_task(self.play_audio()),
                asyncio.create_task(self.idle_watchdog()),
            ]
            done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                exc = task.exception()
                if isinstance(exc, ListeningComplete):
                    return
                if exc is None:
                    self.stop_reason = "listening task ended unexpectedly"
                    raise RuntimeError(self.stop_reason)
                raise exc
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await self._set_assistant_speaking(False)
            if self.audio_stream:
                self.audio_stream.close()
            self.pya.terminate()
            print(f"[listening] Exited: {self.stop_reason}.", flush=True)

    async def listen_audio(self) -> None:
        assert self.out_queue is not None
        mic_info = _input_device_info(self.pya, self.input_device_index)
        if self.debug:
            print(f"[debug] mic: index={mic_info['index']} name={mic_info['name']!r}", flush=True)

        def open_and_start_mic():
            stream = self.pya.open(
                format=self.pyaudio.paInt16,
                channels=CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                input_device_index=mic_info["index"],
                frames_per_buffer=CHUNK_SIZE,
            )
            stream.start_stream()
            return stream

        self.audio_stream = await asyncio.to_thread(open_and_start_mic)
        read_kwargs = {"exception_on_overflow": False} if __debug__ else {}
        for _ in range(15):
            await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **read_kwargs)

        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **read_kwargs)
            if self._mic_send_silence:
                data = b"\x00" * len(data)
            await self.out_queue.put({"data": data, "mime_type": MIC_MIME})

    async def send_realtime(self) -> None:
        assert self.out_queue is not None
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(audio=msg)
            self._send_chunks += 1
            if self.debug and self._send_chunks % 50 == 0:
                data = msg.get("data") or b""
                print(
                    f"[debug] sent mic chunks={self._send_chunks} last_bytes={len(data)} rms={pcm_rms_int16(data):.1f}",
                    flush=True,
                )

    async def receive_audio(self) -> None:
        assert self.audio_in_queue is not None
        genai_types = _genai_types()
        while True:
            sent_tool_response = False
            async for response in self.session.receive():
                if response.tool_call and response.tool_call.function_calls:
                    function_responses = []
                    for function_call in response.tool_call.function_calls:
                        if not function_call.id:
                            continue
                        result = handle_tool_call(
                            function_call.name or "",
                            function_call.args or {},
                            self.chores,
                        )
                        function_responses.append(
                            genai_types.FunctionResponse(
                                id=function_call.id,
                                name=function_call.name or "",
                                response={"result": result},
                            )
                        )
                    if function_responses:
                        await self.session.send_tool_response(function_responses=function_responses)
                        sent_tool_response = True
                        break

                if data := response.data:
                    self._mic_send_silence = True
                    await self._set_assistant_speaking(True)
                    self._cancel_mic_reopen()
                    await self.audio_in_queue.put(data)
                    continue

                if text := response.text:
                    print(text, end="", flush=True)

                server_content = response.server_content
                if server_content:
                    if server_content.turn_complete or server_content.interrupted:
                        self._mic_send_silence = False
                    if server_content.input_transcription and server_content.input_transcription.text:
                        self._last_user_activity = time.monotonic()
                        user_text = server_content.input_transcription.text
                        print(f"\n[you] {user_text}", end="", flush=True)
                        if _should_stop_listening(user_text):
                            self.stop_reason = "stop phrase heard"
                            raise ListeningComplete()
                    if server_content.output_transcription and server_content.output_transcription.text:
                        response_text = server_content.output_transcription.text
                        print(response_text, end="", flush=True)
                        await _notify_text(self.on_assistant_response_text, response_text)
                    if server_content.interrupted:
                        _drain_audio_queue(self.audio_in_queue)
                        self._cancel_mic_reopen()
                        self._mic_send_silence = False
                        await self._set_assistant_speaking(False)

            if sent_tool_response:
                continue
            self._mic_send_silence = False

    async def idle_watchdog(self) -> None:
        while True:
            await asyncio.sleep(min(self.idle_timeout_seconds, 5.0))
            idle_for = time.monotonic() - self._last_user_activity
            if idle_for >= self.idle_timeout_seconds:
                self.stop_reason = f"idle timeout after {self.idle_timeout_seconds:.0f}s"
                raise ListeningComplete()

    async def play_audio(self) -> None:
        assert self.audio_in_queue is not None
        speaker = _output_device_info(self.pya, self.output_device_index)

        def open_and_start_playback():
            stream = self.pya.open(
                format=self.pyaudio.paInt16,
                channels=CHANNELS,
                rate=RECEIVE_SAMPLE_RATE,
                output=True,
                output_device_index=speaker["index"],
                frames_per_buffer=CHUNK_SIZE,
            )
            stream.start_stream()
            return stream

        stream = await asyncio.to_thread(open_and_start_playback)
        try:
            while True:
                bytestream = await self.audio_in_queue.get()
                await asyncio.to_thread(stream.write, bytestream)
                if self.audio_in_queue.empty():
                    self._schedule_mic_reopen()
        finally:
            self._cancel_mic_reopen()
            await asyncio.to_thread(stream.stop_stream)
            await asyncio.to_thread(stream.close)

    def _cancel_mic_reopen(self) -> None:
        if self._mic_reopen_task and not self._mic_reopen_task.done():
            self._mic_reopen_task.cancel()
        self._mic_reopen_task = None

    def _schedule_mic_reopen(self, delay_s: float = 0.35) -> None:
        self._cancel_mic_reopen()

        async def reopen_after_quiet_playback() -> None:
            try:
                await asyncio.sleep(delay_s)
                if self.audio_in_queue is not None and self.audio_in_queue.empty():
                    self._mic_send_silence = False
                    await self._set_assistant_speaking(False)
            except asyncio.CancelledError:
                pass

        self._mic_reopen_task = asyncio.create_task(reopen_after_quiet_playback())

    async def _set_assistant_speaking(self, active: bool) -> None:
        if self._assistant_speaking == active:
            return
        self._assistant_speaking = active
        await _notify_connection(self.on_assistant_speaking, active)


async def run_live(
    client,
    chores: SpeechChoresApi,
    *,
    debug: bool,
    input_device_index: int | None,
    output_device_index: int | None,
    idle_timeout_seconds: float,
    on_connection_active: ConnectionCallback | None = None,
    on_assistant_speaking: ConnectionCallback | None = None,
    on_assistant_response_text: TextCallback | None = None,
) -> None:
    last_error: BaseException | None = None
    session = None
    session_context = None
    connection_marked_active = False
    exit_error: BaseException | None = None
    for model in MODELS:
        try:
            print(f"Connecting with model: {model}", flush=True)
            session_context = client.aio.live.connect(model=model, config=_build_config(model))
            session = await session_context.__aenter__()
            break
        except BaseException as error:
            last_error = error
            if session_context is not None:
                await session_context.__aexit__(type(error), error, error.__traceback__)
                session_context = None
            if model == MODELS[-1]:
                raise
            print(f"Model {model!r} failed ({error!r}); trying fallback.", flush=True)
    if session is None:
        raise RuntimeError("No Live session established.") from last_error
    try:
        await _notify_connection(on_connection_active, True)
        connection_marked_active = True
        await _send_initial_greeting(session)
        loop = AudioLoop(
            session,
            chores,
            debug=debug,
            input_device_index=input_device_index,
            output_device_index=output_device_index,
            idle_timeout_seconds=idle_timeout_seconds,
            on_assistant_speaking=on_assistant_speaking,
            on_assistant_response_text=on_assistant_response_text,
        )
        try:
            await loop.run()
        except BaseException as error:
            exit_error = error
            raise
        finally:
            if connection_marked_active:
                await _notify_connection(on_connection_active, False)
    finally:
        if session_context is not None:
            try:
                await asyncio.wait_for(
                    session_context.__aexit__(
                        type(exit_error) if exit_error else None,
                        exit_error,
                        exit_error.__traceback__ if exit_error else None,
                    ),
                    timeout=GEMINI_SESSION_CLOSE_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                print(
                    "[listening] Gemini session close timed out; returning to wake-word mode.",
                    flush=True,
                )


def _build_config(model: str) -> dict:
    config: dict = {
        "system_instruction": SYSTEM_INSTRUCTION,
        "response_modalities": ["AUDIO"],
        "tools": build_tools(),
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": VOICE_NAME,
                }
            }
        },
        "input_audio_transcription": {},
        "output_audio_transcription": {},
    }
    if "2.5-flash-native-audio-preview" in model:
        config["proactivity"] = {"proactive_audio": True}
    return config


async def _send_initial_greeting(session) -> None:
    await session.send_client_content(
        turns={
            "role": "user",
            "parts": [{"text": INITIAL_GREETING_PROMPT}],
        },
        turn_complete=True,
    )


def _should_stop_listening(transcript: str) -> bool:
    text = transcript.casefold()
    return any(phrase in text for phrase in STOP_LISTENING_PHRASES)


async def _notify_connection(callback: ConnectionCallback | None, active: bool) -> None:
    if callback is None:
        return
    result = callback(active)
    if result is not None:
        await result


async def _notify_text(callback: TextCallback | None, text: str) -> None:
    if callback is None:
        return
    result = callback(text)
    if result is not None:
        await result


def _drain_audio_queue(queue: asyncio.Queue[bytes]) -> None:
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            break


def _pyaudio():
    import pyaudio

    return pyaudio


def _genai_types():
    from google.genai import types

    return types

