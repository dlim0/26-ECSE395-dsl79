> **Current November 23 firmware and test status:** [Read the updated handoff](../FinalReportCode/CURRENT_STATE_2026-11-23.md). The older descriptions below are historical and may describe the superseded growth-only detector.

# Test evidence: current results and historical experiments

Open [index.html](index.html) locally after downloading/cloning to browse every saved session. Dates in filenames retain the original recorded labels. Do not treat successive frames as independent accuracy trials.

## Current 10% + growth firmware (October 31)

| Trial | Changed-region area | Frames | Observed result |
|---|---|---|---|
| [stationary-no-approach](captures/20261031-183457-917906-stationary-no-approach/index.html) | 16.250-16.375% | 10 | No alarm; large but no growth |
| [approaching-growth-test](captures/20261031-183551-894064-approaching-growth-test/index.html) | 15.000 -> 32.646% | 5 + 10 empty | Alarm on fifth growing frame; stopped; empty follow-up rejected |
| [centered-small-target-repeat](captures/20261031-183751-692936-centered-small-target-repeat/index.html) | 3.792-7.458% | 10 | No alarm; small object visible |

No device/transport errors in these runs. The first small-change run reached only 1.062% with the target mostly at the edge; use the visible-object repeat above as stronger evidence. A narrow object was used as a large/approaching surrogate, not an actual deer. Buzzer was disconnected during later tests; alarm logs show commands, not audible sound.

## Earlier stages

- [Classifier attempt](../experiments/deer-classifier/README.md): on-device execution succeeded, deer-image recognition did not meet threshold.
- 3% then 5% size-only trials: phone/person separation in a fixed scene; false positives later appeared around 5.4-5.8% in an apparently empty scene, motivating the growth pivot.
- [Sound + RGB trial](captures/20261031-163535-273574-final-rgb-large-target/index.html): user confirmed sound/white flashes then both stopping under earlier size-only firmware.
- [Camera diagnostic](captures/20261031-180337-326915-d12-camera-diagnostic/index.html): eight checksum-verified images; normal firmware was subsequently restored. CAMERA_TEST area=0 is a placeholder, not a detector measurement.
- [Approach startup](captures/20261031-183354-551487-approach-10-percent-startup/index.html): embedded tests PASS, seven saved photos, calibration completed.

Full chronology, partial-recording caveats and earlier numeric results are preserved in [HISTORY.md](HISTORY.md). Earlier thresholds/firmware descriptions there are historical. Camera movement requires a new reference. No matched flash-off comparison quantifies illumination gain.

## Power and outdoor evidence status

User confirmed complete battery-only operation in conversation. No host recording can prove the offline segment, and no measured current/runtime was provided. Outdoor work was to be self-documented; no observations or field accuracy claims have been added. Use [the log template](../FinalReportCode/OUTDOOR_TEST_LOG.csv) when those results arrive.
