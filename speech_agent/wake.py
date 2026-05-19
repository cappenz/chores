from __future__ import annotations

from speech_agent.audio import CHUNK_SIZE, CHANNELS, SEND_SAMPLE_RATE, PortAudioRuntime, _input_device_info


async def wait_for_wake_word(
    audio_runtime: PortAudioRuntime,
    *,
    input_device_index: int | None,
    wake_model: str,
    wake_config: str | None,
    debug: bool,
) -> None:
    MicroWakeWord, MicroWakeWordFeatures, WakeModel = _wake_imports()
    pyaudio = audio_runtime.pyaudio
    stream = None
    detector = None
    try:
        def get_mic_info():
            return _input_device_info(audio_runtime.pya, input_device_index)

        mic_info = await audio_runtime.run(get_mic_info)
        if wake_config:
            detector = MicroWakeWord.from_config(wake_config)
        else:
            detector = MicroWakeWord.from_builtin(WakeModel(wake_model))
        features = MicroWakeWordFeatures()
        if debug:
            print(f"[debug] wake mic: index={mic_info['index']} name={mic_info['name']!r}", flush=True)
        print(f"[sleeping] Waiting for wake word: {wake_config or wake_model}", flush=True)

        def open_and_start_mic():
            mic_stream = audio_runtime.pya.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                input_device_index=mic_info["index"],
                frames_per_buffer=CHUNK_SIZE,
            )
            mic_stream.start_stream()
            return mic_stream

        stream = await audio_runtime.run(open_and_start_mic)
        read_kwargs = {"exception_on_overflow": False} if __debug__ else {}
        for _ in range(15):
            await audio_runtime.run(stream.read, CHUNK_SIZE, **read_kwargs)

        while True:
            data = await audio_runtime.run(stream.read, CHUNK_SIZE, **read_kwargs)
            for feature_frame in features.process_streaming(data):
                if detector.process_streaming(feature_frame):
                    print("[wake] Wake word detected; entering listening mode.", flush=True)
                    return
    finally:
        if stream:
            await audio_runtime.run(stream.stop_stream)
            await audio_runtime.run(stream.close)
        if detector:
            detector.close()


def _wake_imports():
    from pymicro_wakeword import MicroWakeWord, MicroWakeWordFeatures, Model as WakeModel

    return MicroWakeWord, MicroWakeWordFeatures, WakeModel

