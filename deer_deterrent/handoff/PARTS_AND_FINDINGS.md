# What happened, by project part

| Part | Goal and change | Finding | Where to look |
|---|---|---|---|
| 1. Original PIR + buzzer lab | Learn motion input and passive-buzzer control on Feather ESP32 V2 | Basic integration worked; repeated triggers were observed. A fan was suspected, not proven to be the cause | Existing [Lab 5](../../Lab%205/) |
| 2. ESP32-S3 + OV5640 bring-up | Move to TFT Feather, wire parallel camera, view/download pictures over local Wi-Fi, then PIR-trigger bursts | Camera capture worked. Unpowered camera, misplaced clock wire and header-label confusion were resolved during bring-up. The archived source is historical and uses the TFT | [Camera prototype](../experiments/camera-wifi-bringup/README.md), [current wiring](../WIRING.md) |
| 3. Deer recognition attempt | Reuse the team's ESP-DL model on the S3 rather than requiring a connected PC | Model ran, observed inference about 378-379 ms. Full-body mean/max 0.2163/0.3775; close-up 0.0827/0.2227; 33 frames each; neither confirmed at 0.85 | [Classifier results](../experiments/deer-classifier/README.md), raw JSON under its test-results folder |
| 4. Size-filter MVP | Compare largest changed region with a fixed empty reference; test phone/person surrogates; increase cutoff from 3% to 5% | Indoor separation demonstrated, with documented confounds (phone plus forearm). Later empty/background regions around 5.4-5.8% retriggered the size-only rule | [Historical tests](../tests/HISTORY.md), [false-positive gallery](../tests/captures/20261031-182520-584322-large-target-recorded-repeat/index.html) |
| 5. Photo lighting + deterrent | White before/through capture; 5 Hz white alarm flashes plus three buzzer pulses | Earlier user-confirmed sound and light started/stopped. Capture illumination uses RGB13/36/35; TFT disabled. No matched flash-off comparison establishes illumination gain | [Wiring](../WIRING.md), [sound/light trial](../tests/captures/20261031-163535-273574-final-rgb-large-target/index.html) |
| 6. Camera/PIR debugging | Loose camera D3-to-D12 wire; PIR read HIGH; camera-only diagnostic; then normal firmware restored | Eight fresh diagnostic images confirmed capture. User later found PIR power/ground reversed; subsequent LOW/HIGH readings and capture sequences were observed. A camera move changed the reference; recalibration gave ten 0% frames | [Diagnostic gallery](../tests/captures/20261031-180337-326915-d12-camera-diagnostic/index.html), [runbook](RUNBOOK.md) |
| 7. Approaching-object pivot | Add 10% floor plus growth instead of treating every persistent large change as a target | Stationary large target rejected; growing large target accepted; visible small-object repeat rejected. Exact rules and evidence below | [Current tests](../tests/README.md), [gate source](../firmware/motion-size/src/approach_gate.hpp) |
| 8. Power/outdoor continuation | Operate independently of USB, then test outdoors | User confirmed complete battery-only operation. No measured runtime/current or outdoor observations are available in the saved evidence | [Outdoor log template](OUTDOOR_TEST_LOG.csv), [known issues](KNOWN_ISSUES.md) |

## Final recorded indoor comparison

| Trial | Largest changed-region area | Outcome |
|---|---|---|
| Stationary large object | 16.250-16.375% across ten frames | No growth confirmation, no alarm |
| Approaching object | 15.000 -> 18.042 -> 23.375 -> 28.208 -> 32.646% | Confirmed on fifth frame; alarm ON/OFF; rearmed without timed cooldown |
| Empty scene immediately after approach | Ten frames at 0% | No second alarm; normal unconfirmed-window cooldown |
| Visible small-object repeat | 3.792-7.458% across ten frames | No alarm, below 10% floor despite area growth |

Scores from the model are not calibrated probabilities. Exact model inputs in the framing comparison were not independently saved/verified. Changed-region percentages are pixel area, not bounding-box area or physical body size. Apparent-size growth is a useful heuristic; it does not prove approach direction, identity or deer presence.
