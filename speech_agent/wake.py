from __future__ import annotations

import asyncio

from speech_agent.audio import CHUNK_SIZE, CHANNELS, SEND_SAMPLE_RATE, _input_device_info


async def wait_for_wake_word(
    *,
    input_device_index: int | None,
    wake_model: str,
    wake_config: str | None,
    debug: bool,
) -> None:
    pyaudio, MicroWakeWord, MicroWakeWordFeatures, WakeModel = _wake_imports()
    pya = pyaudio.PyAudio()
    stream = None
    detector = None
    try:
        mic_info = _input_device_info(pya, input_device_index)
        if wake_config:
            detector = MicroWakeWord.from_config(wake_config)
        else:
            detector = MicroWakeWord.from_builtin(WakeModel(wake_model))
        features = MicroWakeWordFeatures()
        if debug:
            print(f"[debug] wake mic: index={mic_info['index']} name={mic_info['name']!r}", flush=True)
        print(f"[sleeping] Waiting for wake word: {wake_config or wake_model}", flush=True)

        def open_and_start_mic():
            mic_stream = pya.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                input_device_index=mic_info["index"],
                frames_per_buffer=CHUNK_SIZE,
            )
            mic_stream.start_stream()
            return mic_stream

        stream = await asyncio.to_thread(open_and_start_mic)
        read_kwargs = {"exception_on_overflow": False} if __debug__ else {}
        for _ in range(15):
            await asyncio.to_thread(stream.read, CHUNK_SIZE, **read_kwargs)

        while True:
            data = await asyncio.to_thread(stream.read, CHUNK_SIZE, **read_kwargs)
            for feature_frame in features.process_streaming(data):
                if detector.process_streaming(feature_frame):
                    print("[wake] Wake word detected; entering listening mode.", flush=True)
                    return
    finally:
        if stream:
            await asyncio.to_thread(stream.stop_stream)
            await asyncio.to_thread(stream.close)
        if detector:
            detector.close()
        pya.terminate()


def _wake_imports():
    import pyaudio
    from pymicro_wakeword import MicroWakeWord, MicroWakeWordFeatures, Model as WakeModel

    return pyaudio, MicroWakeWord, MicroWakeWordFeatures, WakeModel

