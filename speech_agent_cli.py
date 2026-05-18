from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from chores import ChoresService
from core.people import load_people
from speech_agent.audio import AudioSelfTestConfig, print_audio_devices, run_audio_selftest
from speech_agent.runner import DEFAULT_IDLE_TIMEOUT_SECONDS, DEFAULT_WAKE_MODEL, SpeechAgentConfig, run_speech_agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Kitchen speech agent diagnostics and standalone runner.")
    parser.add_argument("--list-audio-devices", action="store_true")
    parser.add_argument("--audio-selftest", action="store_true")
    parser.add_argument("--selftest-seconds", type=float, default=3.0)
    parser.add_argument("--selftest-wav", default="selftest_mic.wav")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--input-device-index", type=int, default=None)
    parser.add_argument("--output-device-index", type=int, default=None)
    parser.add_argument("--wake-model", default=DEFAULT_WAKE_MODEL)
    parser.add_argument("--wake-config", default=None)
    parser.add_argument("--idle-timeout-seconds", type=float, default=DEFAULT_IDLE_TIMEOUT_SECONDS)
    args = parser.parse_args()

    if args.list_audio_devices:
        print_audio_devices()
        return

    if args.audio_selftest:
        result = run_audio_selftest(
            AudioSelfTestConfig(
                seconds=args.selftest_seconds,
                wav_path=Path(args.selftest_wav),
                input_device_index=args.input_device_index,
                output_device_index=args.output_device_index,
            )
        )
        print(f"Captured {result.captured_bytes} bytes, RMS={result.rms:.1f}, WAV={result.wav_path}")
        return

    people = load_people()
    chores = ChoresService(people=people)
    asyncio.run(
        run_speech_agent(
            chores,
            SpeechAgentConfig(
                debug=args.debug,
                input_device_index=args.input_device_index,
                output_device_index=args.output_device_index,
                wake_model=args.wake_model,
                wake_config=args.wake_config,
                idle_timeout_seconds=args.idle_timeout_seconds,
            ),
        )
    )


if __name__ == "__main__":
    main()
