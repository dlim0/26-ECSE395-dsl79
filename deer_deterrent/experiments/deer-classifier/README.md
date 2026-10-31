# Earlier experiment — on-device deer recognition

Preserved for context; the current MVP is [firmware/motion-size](../../firmware/motion-size/).

The ESP32-S3 ran the 499,712-byte ESP-DL deer model with observed inference around 378–379 ms. Recognition did not pass the demonstration: neither the full-body nor close-up deer-image run reached the 0.85 confirmation threshold. This prompted the pivot to large foreground-change detection. The cause of the misses was not established.

| User-presented view | Frames | Mean score | Max score | Confirmed detections |
|---|---:|---:|---:|---:|
| Full-body deer image | 33 | 0.2163 | 0.3775 | 0 |
| Close-up deer image | 33 | 0.0827 | 0.2227 | 0 |

Scores are not calibrated probabilities; framing was user-reported and exact model-input images were not independently saved/verified. This result does not show that all ESP32 deer classifiers are infeasible.

`src/` contains the diagnostic firmware, `model/` the unchanged model, and [test-results](test-results/) the raw score JSON and startup log. Upstream attribution is in [SOURCES.md](../../SOURCES.md).

Build with `.\build.ps1` from this directory. The Windows helper requires PlatformIO under your user profile and uses V: as a space-free alias, checking for conflicts first. CMake regenerates model_data.S with the local model path. Uploading this diagnostic replaces the current MVP; it does not provide PIR-gated deterrent behavior.
