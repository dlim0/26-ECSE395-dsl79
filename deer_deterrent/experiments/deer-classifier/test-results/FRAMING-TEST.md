# Deer framing comparison

User presented each view for a separate 30-second observation. No independent camera-image verification or randomized repetitions were performed. Scores are detector confidence scores, not calibrated probabilities.

| View | Frames | Mean score | Max score | Confirmed detections |
|---|---:|---:|---:|---:|
| Full body | 33 | 0.2163 | 0.3775 | 0 |
| Close-up | 33 | 0.0827 | 0.2227 | 0 |

Threshold remained 0.85. Full-body scores were higher in this single comparison; neither view passed detection. Do not choose a new threshold from positive examples alone. Capture/inspect the exact model input and collect empty/non-deer controls before tuning.
