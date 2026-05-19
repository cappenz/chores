from __future__ import annotations

import os
import time

import pytest

from speech_agent.audio import CHANNELS, CHUNK_SIZE, RECEIVE_SAMPLE_RATE, SEND_SAMPLE_RATE


pytestmark = pytest.mark.manual


def test_pyaudio_wake_listen_cycle_stress():
    if os.getenv("CHORES_TEST_PYAUDIO_STRESS") != "1":
        pytest.skip("Run with CHORES_TEST_PYAUDIO_STRESS=1 to exercise local audio hardware.")

    import pyaudio

    cycles = int(os.getenv("CHORES_TEST_PYAUDIO_CYCLES", "100"))
    read_chunks = int(os.getenv("CHORES_TEST_PYAUDIO_READ_CHUNKS", "10"))
    write_chunks = int(os.getenv("CHORES_TEST_PYAUDIO_WRITE_CHUNKS", "10"))
    pause_seconds = float(os.getenv("CHORES_TEST_PYAUDIO_PAUSE_SECONDS", "0.05"))

    for cycle in range(1, cycles + 1):
        print(f"\n[pyaudio-stress] cycle {cycle}/{cycles}: wake input", flush=True)
        _run_input_stream(pyaudio, SEND_SAMPLE_RATE, read_chunks)

        print(f"[pyaudio-stress] cycle {cycle}/{cycles}: listen input+output", flush=True)
        _run_duplex_like_streams(pyaudio, read_chunks, write_chunks)

        if pause_seconds > 0:
            time.sleep(pause_seconds)


def _run_input_stream(pyaudio, sample_rate: int, chunks: int) -> None:
    pya = pyaudio.PyAudio()
    stream = None
    try:
        mic = pya.get_default_input_device_info()
        print(
            f"[pyaudio-stress] input index={mic['index']} name={mic['name']!r} "
            f"rate={sample_rate}",
            flush=True,
        )
        stream = pya.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=sample_rate,
            input=True,
            input_device_index=mic["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        stream.start_stream()
        for _ in range(chunks):
            stream.read(CHUNK_SIZE, exception_on_overflow=False)
    finally:
        _stop_close_stream(stream)
        pya.terminate()


def _run_duplex_like_streams(pyaudio, read_chunks: int, write_chunks: int) -> None:
    pya = pyaudio.PyAudio()
    stream_in = None
    stream_out = None
    try:
        mic = pya.get_default_input_device_info()
        speaker = pya.get_default_output_device_info()
        print(
            f"[pyaudio-stress] input index={mic['index']} name={mic['name']!r}; "
            f"output index={speaker['index']} name={speaker['name']!r}",
            flush=True,
        )
        stream_in = pya.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        stream_out = pya.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
            output_device_index=speaker["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        stream_in.start_stream()
        stream_out.start_stream()
        silence = b"\x00" * CHUNK_SIZE * 2 * CHANNELS
        for index in range(max(read_chunks, write_chunks)):
            if index < read_chunks:
                stream_in.read(CHUNK_SIZE, exception_on_overflow=False)
            if index < write_chunks:
                stream_out.write(silence)
    finally:
        _stop_close_stream(stream_in)
        _stop_close_stream(stream_out)
        pya.terminate()


def _stop_close_stream(stream) -> None:
    if stream is None:
        return
    try:
        stream.stop_stream()
    finally:
        stream.close()
