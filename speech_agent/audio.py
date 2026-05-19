from __future__ import annotations

import array
import math
import platform
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHANNELS = 1
CHUNK_SIZE = 1024


@dataclass(frozen=True)
class AudioSelfTestConfig:
    seconds: float = 3.0
    wav_path: Path = Path("selftest_mic.wav")
    input_device_index: int | None = None
    output_device_index: int | None = None


@dataclass(frozen=True)
class AudioSelfTestResult:
    wav_path: Path
    captured_bytes: int
    rms: float


def print_audio_devices() -> None:
    pyaudio = _pyaudio()
    pya = pyaudio.PyAudio()
    try:
        try:
            device = pya.get_default_input_device_info()
            print(f"Default INPUT:  index {device['index']} - {device['name']}", flush=True)
        except OSError as error:
            print(f"Default INPUT:  (none) - {error}", flush=True)
        try:
            device = pya.get_default_output_device_info()
            print(f"Default OUTPUT: index {device['index']} - {device['name']}", flush=True)
        except OSError as error:
            print(f"Default OUTPUT: (none) - {error}", flush=True)
        print("", flush=True)
        for index in range(pya.get_device_count()):
            info = pya.get_device_info_by_index(index)
            inputs = int(info.get("maxInputChannels", 0))
            outputs = int(info.get("maxOutputChannels", 0))
            if inputs == 0 and outputs == 0:
                continue
            flags = []
            if inputs:
                flags.append(f"in:{inputs}ch")
            if outputs:
                flags.append(f"out:{outputs}ch")
            print(
                f"  [{index:3d}] {info['name'][:72]} | {', '.join(flags)} | defaultSR={info.get('defaultSampleRate')}",
                flush=True,
            )
    finally:
        pya.terminate()


def run_audio_selftest(config: AudioSelfTestConfig) -> AudioSelfTestResult:
    pyaudio = _pyaudio()
    total_frames = int(SEND_SAMPLE_RATE * config.seconds)
    total_bytes = total_frames * 2 * CHANNELS
    pya = pyaudio.PyAudio()
    try:
        mic = _input_device_info(pya, config.input_device_index)
        spk = _output_device_info(pya, config.output_device_index)
        print(f"Using INPUT:  {mic['name']} (index {mic['index']})", flush=True)
        print(f"Using OUTPUT: {spk['name']} (index {spk['index']})", flush=True)
        stream_in = pya.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        stream_in.start_stream()
        read_kw = {"exception_on_overflow": False} if __debug__ else {}
        for _ in range(15):
            stream_in.read(CHUNK_SIZE, **read_kw)

        chunks: list[bytes] = []
        got = 0
        while got < total_bytes:
            chunk = stream_in.read(CHUNK_SIZE, **read_kw)
            chunks.append(chunk)
            got += len(chunk)
        stream_in.stop_stream()
        stream_in.close()

        pcm = b"".join(chunks)[:total_bytes]
        rms = pcm_rms_int16(pcm)
        with wave.open(str(config.wav_path), "wb") as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(2)
            wav_file.setframerate(SEND_SAMPLE_RATE)
            wav_file.writeframes(pcm)

        stream_out = pya.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            output=True,
            output_device_index=spk["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        stream_out.start_stream()
        stream_out.write(pcm)
        stream_out.stop_stream()
        stream_out.close()
        return AudioSelfTestResult(config.wav_path, len(pcm), rms)
    finally:
        pya.terminate()


def pcm_rms_int16(data: bytes) -> float:
    if not data:
        return 0.0
    samples = array.array("h")
    samples.frombytes(data)
    if not samples:
        return 0.0
    acc = sum(sample * sample for sample in samples)
    return math.sqrt(acc / len(samples))


def open_macos_microphone_privacy() -> None:
    if platform.system() != "Darwin":
        print("This shortcut is only available on macOS.", flush=True)
        return
    urls = (
        "x-apple.systemsettings:com.apple.settings.PrivacySecurity.extension?path=Privacy/Microphone",
        "x-apple.systemsettings:com.apple.preference.security?Privacy_Microphone",
        "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
    )
    for url in urls:
        result = subprocess.run(["open", url], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Opened System Settings via: {url}", flush=True)
            return
    print("Could not run `open` to show Microphone settings.", flush=True)


def _input_device_info(pya, index: int | None) -> dict:
    if index is not None:
        return pya.get_device_info_by_index(index)
    return pya.get_default_input_device_info()


def _output_device_info(pya, index: int | None) -> dict:
    if index is not None:
        return pya.get_device_info_by_index(index)
    return pya.get_default_output_device_info()


def _pyaudio():
    import pyaudio

    return pyaudio

