# Reachy Mini Component

## Purpose

The `reachy/` directory owns Reachy Mini companion behavior for the kitchen assistant. It turns speech lifecycle events into robot presence: wake and sleep poses, face tracking while awake, short emotional reactions, and subtle motion while the assistant voice is speaking.

Reachy behavior includes:

- wake up when the speech assistant wakes up
- return to a sleep posture when the speech assistant sleeps
- track nearby faces while the assistant is awake and waiting or listening
- show short emotional reactions during assistant responses
- move subtly while the computer voice is speaking

## Responsibilities

Reachy connects to the local Reachy Mini daemon through the official `reachy-mini` SDK, owns robot motion and camera behavior, and exposes an async-friendly API to the application supervisor. Hardware is optional: when Reachy is disabled or unavailable, the app logs the condition once and the rest of the app keeps running through a no-op companion.

Reachy does not own chore state, Gemini tools, Discord, display widgets, speech recognition, microphone input, speaker playback, or WebRTC runtime behavior.

## Architecture

Reachy is an adapter component started by the top-level application supervisor. The speech agent emits generic lifecycle events, and the supervisor forwards those events to the Reachy companion. The speech agent does not import `reachy/`.

The Reachy daemon is a local process controlling either the USB robot or the MuJoCo simulator. The chores app uses the same local SDK connection for both.

## Public API

The component exposes:

- `run_reachy_companion(config: ReachyConfig) -> ReachyCompanion`: start the companion and return the narrow control interface.
- `ReachyCompanion.wake() -> Awaitable[None]`: transition from sleep to an attentive awake posture and enable face tracking.
- `ReachyCompanion.sleep() -> Awaitable[None]`: stop tracking and move to the Reachy sleep posture.
- `ReachyCompanion.set_speaking(active: bool) -> Awaitable[None]`: start or stop subtle speech-reactive motion.
- `ReachyCompanion.show_emotion(emotion: ReachyEmotion) -> Awaitable[None]`: enqueue a short emotion move that can complete even after the assistant returns to listening.
- `ReachyCompanion.close() -> Awaitable[None]`: stop loops, cancel queued motion, and release SDK resources.

The speech agent lifecycle callbacks are generic and robot-independent:

- `on_assistant_awake(active: bool)`
- `on_assistant_speaking(active: bool)`
- `on_assistant_response_text(text: str)`

## Runtime States

- `disabled`: Reachy integration is off by configuration.
- `unavailable`: Reachy is enabled but SDK import, daemon connection, or hardware connection failed; the public API behaves as a no-op companion.
- `sleeping`: the robot is in a sleep posture and tracking/speaking/emotion behavior is stopped.
- `awake`: the robot is in an attentive posture and face tracking is the default background behavior.
- `speaking`: the assistant is playing model audio and Reachy adds subtle head, antenna, or body motion.
- `emotion`: Reachy is playing a short recorded or procedural emotional move; face tracking is suspended for the emotion.

## Motion Model

All motor commands pass through one motion owner inside `reachy/`. Sleep/wake transitions, emotional moves, speaking motion, and face tracking update a shared desired state. The motion owner resolves that state into SDK commands so background loops do not independently command the same motors.

## Face Tracking

Face tracking is a rate-limited background vision loop active in the `awake` state. The loop reads frames from the Reachy camera, detects nearby faces, chooses a target face, smooths the target over time, and sends a look target to the motion owner. It runs at a bounded cadence, initially around 8 detections per second, and drops stale frames rather than trying to process every camera frame.

The normal frame source is `mini.media.get_frame()` without Reachy audio. Direct OpenCV camera capture is the fallback when SDK media conflicts with host audio.

## Emotions

The component exposes a curated local emotion enum:

- `happy`
- `curious`
- `thinking`
- `confused`
- `celebrate`
- `sad`

Each emotion maps to either a recorded move from `pollen-robotics/reachy-mini-emotions-library` or a procedural head/antenna/body motion. The public API uses the local enum rather than raw dataset move names, even though the upstream library contains many more recorded moves.

Gemini does not directly control arbitrary robot motion. Robot-facing tools expose safe, named emotions only.

## Media Ownership

The speech agent owns microphone input in sleeping and listening modes, and owns speaker playback during Gemini Live responses. Reachy uses robot motion and camera frames only; it does not use Reachy microphone, speaker, or direction-of-arrival APIs in normal app runtime.

## Simulator Testing

The Reachy Mini MuJoCo simulator runs behind the same local daemon interface as the USB robot. Simulator checks cover SDK connection and motion behavior through the normal `ReachyCompanion` API. They are manual integration checks, not part of `make test`, and they do not validate USB behavior, camera quality, audio coexistence, or physical safety.

## Configuration

Runtime configuration includes:

- enable or disable Reachy integration
- connection mode fixed to localhost/USB
- simulator/manual-test mode
- face tracking enabled
- emotion playback enabled
- speaking motion enabled
- debug logging

Reachy SDK imports are lazy so a developer without Reachy dependencies can run normal tests and non-robot app paths.

## Testing

Automated tests use fake SDK clients and synthetic vision inputs. They do not import the real SDK at module import time, require a daemon, open camera or audio devices, play speaker audio, connect to Gemini, or call paid services. Real hardware and simulator checks are manual tests.

