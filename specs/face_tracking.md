# Face Tracking and Recognition

## Purpose

Face tracking turns Reachy Mini camera frames into stable face targets for robot
attention. It should favor precision over recall: a missed face is better than
tracking a bottle, cabinet edge, or other face-like kitchen object.

This spec also defines the detection output needed for a later face recognition
pipeline. Recognition is not required for the first implementation step, but the
detector should produce landmarks and aligned crops so recognition can be added
without replacing the tracking pipeline.

## Component Boundary

The `reachy/` component owns face tracking because it owns Reachy camera access
and robot motion. The Reachy Mini daemon and SDK provide camera frames only; they
do not provide face detections, landmarks, identities, or tracking decisions.

The normal frame source is:

- `ReachyMini(...).media.get_frame()`
- return type: `numpy.ndarray | None`
- frame layout: OpenCV BGR image, shape `(height, width, 3)`, dtype `uint8`
- `None` means the camera is unavailable or no frame is ready

Face tracking code must treat daemon frames as BGR. OpenCV detector inputs may
use the BGR frame directly unless a specific model API says otherwise. Any saved
images, PIL images, browser-visible previews, or model inputs that require RGB
must convert explicitly from BGR to RGB first.

If a real-world orange object appears blue in a saved sample, that is evidence
that the BGR frame was handed to an RGB consumer without conversion. The camera
frame itself should not be fixed globally; conversion should happen at the
boundary where RGB is required.

## Detection Model

Use OpenCV YuNet as the default face detector. It is a better fit than Haar
cascades because it provides confidence scores and five facial landmarks while
remaining lightweight enough for a dedicated Mac Mini.

Detector output should include:

- bounding box in source-frame pixels: `x`, `y`, `width`, `height`
- confidence score
- five landmarks in source-frame pixels:
  - left eye
  - right eye
  - nose tip
  - left mouth corner
  - right mouth corner
- normalized tracking target:
  - `x`: `-1.0` left, `0.0` center, `1.0` right
  - `y`: `-1.0` top, `0.0` center, `1.0` bottom
- optional aligned face crop for sample collection or recognition

The YuNet model file is small enough to check into the repository. The loader
should use the checked-in artifact, document the source URL near the loader, and
verify a documented checksum before use.

## Detection Policy

Default tuning should prefer reliable positives:

- reject detections below a configurable confidence threshold, initially around
  `0.75` to `0.85`
- reject tiny faces below a configurable minimum pixel size
- reject implausible aspect ratios or boxes clipped too tightly to frame edges
- choose the best target by confidence and size, with bias toward the current
  tracked face to avoid unnecessary jumps
- run at a bounded cadence, initially around 2 detections per second
- drop stale frames instead of building a backlog

The exact thresholds are configuration values owned by `reachy/`, not Gemini
tools or speech-agent state.

## Temporal Tracking

Single-frame detections are not enough to move the robot. The tracker should
maintain a short-lived track state:

- require a new face to appear in at least 2 of the last 3 detection cycles
  before it becomes the active target
- keep an active target through brief misses for a small grace window
- smooth target coordinates before converting them to head motion
- reject sudden large jumps unless the previous target has been lost
- stop face detection and face tracking while Reachy is sleeping
- stop commanding face tracking while Reachy is playing an emotion or otherwise
  under another motion mode

Motion conversion remains conservative:

- map normalized horizontal target to bounded yaw
- map normalized vertical target to bounded pitch
- continue using the shared Reachy motion owner so background loops do not fight
  over motors

## Recognition-Ready Face Samples

Face sample collection should save data that is useful for recognition:

- original frame size
- detection box
- confidence
- landmarks
- crop box
- aligned crop path when available
- source: `reachy`
- capture timestamp
- optional track id for grouping adjacent samples

Saved crops should be aligned using the detector landmarks. Alignment should be
deterministic so the same face pose produces comparable recognition inputs.

Collecting many unlabeled samples is acceptable; disk space is not the primary
constraint. The first implementation should focus on preserving useful metadata
and correct color conversion rather than aggressively limiting sample volume.

Samples are unlabeled by default. A later labeling workflow can associate crops
with known people from `core/people` or another public people API, but `reachy/`
must not reach into unrelated component internals.

## Future Recognition Pipeline

The next recognition step should use embeddings rather than direct image
comparison. The preferred simple stack is:

1. YuNet detection and landmarks
2. landmark-based alignment
3. OpenCV SFace or another ArcFace-style embedding model
4. nearest-neighbor matching against labeled household embeddings
5. confidence and margin checks before accepting an identity

Identity results should be separate from detection results:

- detection answers "where is a reliable face?"
- recognition answers "whose face is this, if known?"

Robot tracking may use reliable detections without identity. Any user-facing
identity behavior must include an explicit unknown state and should avoid acting
on low-confidence matches.

## Testing

Regular automated tests should not require the Reachy daemon, camera hardware,
model downloads, model artifacts, or representative image datasets. They should
cover pure logic:

- parsing YuNet outputs into local detection objects
- BGR/RGB conversion behavior for model input and saved crops
- confidence, size, and aspect-ratio filtering
- temporal promotion from candidate to active target
- smoothing and jump rejection
- sample metadata fields for boxes, landmarks, and aligned crops

Model validation for this step should only prove that the model can be obtained,
loaded, and called without raising an error. These tests should be marked with
the pytest `model` marker and run through `make test-model`, not through the
regular `make test` suite. They should use the checked-in model artifact but
should not check whether the detector works correctly yet because there is no
representative face/non-face fixture dataset.

Manual tests may use the real Reachy camera or simulator and should be explicit
entry points outside `make test`.
