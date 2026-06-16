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

Face tracking code must treat daemon frames as BGR. Any saved images or model
inputs that require RGB must convert explicitly.

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

The model file should be managed as a local artifact with a clear source URL and
checksum documented near the loader. It should not be downloaded during normal
runtime.

## Detection Policy

Default tuning should prefer reliable positives:

- reject detections below a configurable confidence threshold, initially around
  `0.75` to `0.85`
- reject tiny faces below a configurable minimum pixel size
- reject implausible aspect ratios or boxes clipped too tightly to frame edges
- choose the best target by confidence and size, with bias toward the current
  tracked face to avoid unnecessary jumps
- run at a bounded cadence, initially around 8 detections per second
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
- stop commanding face tracking while Reachy is sleeping, playing an emotion, or
  otherwise under another motion mode

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

Automated tests should not require the Reachy daemon, camera hardware, or model
downloads. They should cover:

- parsing YuNet outputs into local detection objects
- BGR/RGB conversion behavior for model input and saved crops
- confidence, size, and aspect-ratio filtering
- temporal promotion from candidate to active target
- smoothing and jump rejection
- sample metadata fields for boxes, landmarks, and aligned crops

Manual tests may use the real Reachy camera or simulator and should be explicit
entry points outside `make test`.
