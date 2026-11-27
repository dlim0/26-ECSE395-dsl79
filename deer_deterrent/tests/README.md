# Saved detector evidence

Open the [session index](index.html) locally from a complete checkout or download. Each session retains its original JPEGs, metadata, event log, summary and gallery. Filenames preserve their recorded labels. A sequence of pictures from one scene is not a set of independent accuracy trials.

## November 23 fusion session

[Outside-dark inspection](captures/20261123-002523-561342-outside-dark-inspection/index.html) contains eighteen JPEGs, eighteen sidecars, [103 event rows](captures/20261123-002523-561342-outside-dark-inspection/events.jsonl), a [summary](captures/20261123-002523-561342-outside-dark-inspection/summary.json) and its original gallery. The [dated handoff](../FinalReportCode/CURRENT_STATE_2026-11-23.md) describes the hardware session and the current [fusion rule](../firmware/motion-size/README.md#image-rule).

The first observed camera burst has eight frames, 46–53. The last three score pairs are:

| Frame | Grayscale area | Assisted union area | Recorded state |
|---:|---:|---:|---|
| 51 | 5.042% | 6.750% | SMALL_CHANGE |
| 52 | 7.271% | 9.354% | CONFIRMING |
| 53 | 7.688% | 9.417% | LARGE_CHANGE |

Frames 52 and 53 pass the 7% grayscale threshold. The log records `DETERRENT_ON frame=53` and `BURST_END frames=8 large_confirmed=1`, followed by output completion and a configured 4,500 ms cooldown message. All eighteen assisted scores are below 10%, so no assisted-only activation is demonstrated. Assisted area is the grayscale/color union, not a separate color-only measurement.

The second camera burst has ten frames, 54–63, none qualifying. It ends with `large_confirmed=0` and no timed post-miss pause. The retained sequence has these boundaries:

- It starts at a vibration receipt and camera initialization; the first burst's preceding PIR opening is absent.
- The second burst includes its PIR wait, vibration receipt, camera frames and rejection.
- The final row opens another PIR/vibration wait, whose outcome is not retained. The summary's last ARMED heartbeat precedes that event and is not an unqualified final system state.

The pictures show the hand presentations described by the dated note. The software output events do not independently measure sound, optical flashes or elapsed physical output duration. The eighteen selected-region measurements equal grayscale in this run; the assisted percentages and enable flag are retained separately in `DETECTION_SCORES` messages. A JPEG/sidecar pair alone does not carry all of that context.

### Preserve the original record's limits

The original gallery says confirmation takes three frames. That caption does not describe the current two-frame rule or the recorded frame 52/53 transition; it is retained as part of the original artifact. The current recorder source does not contain that fixed three-frame caption. New recordings have their own output directories and should be interpreted using their received metadata and the current [tools guide](../tools/README.md).

This chunk includes neither startup/calibration pictures nor `DETECTION_MODE`, a source commit, binary hash, boot identifier, run manifest or raw serial file. The recorded enable flags and twelve baseline samples do not establish the note's 100%-dark calibration figure by themselves. The exact learned reference cannot be reconstructed by selecting an apparently empty operational picture.

The dated note separately reports the earlier unsaved zero-score burst, connection/JPEG recovery, black-jacket miss and cardboard success. Those reports are not independently present in this saved chunk. No trial denominator, measured distance, verified cardboard score, deer-detection rate, deterrence result or runtime follows from them. Matching message vocabulary and thresholds support compatibility with the supplied source, not unique identity of the flashed binary.

## November outdoor observations

The [outdoor observation log](../FinalReportCode/OUTDOOR_TEST_LOG.csv) contains four labeled November 23 accounts. The entries distinguish saved serial evidence, serial observations summarized in the dated account, and reports without matched recordings.

| Entry | Observation | Evidence boundary |
|---|---|---|
| NIGHT-01 | An earlier burst, frames 26–35, reported zero grayscale and assisted scores | Serial observations are summarized in the dated account; no images from this burst were saved |
| NIGHT-02 | Illuminated hand; grayscale confirmation on frame 53 | The retained JPEGs, sidecars and event log support the sequence described above |
| NIGHT-03 | Reported black-jacket miss | No independently matched recording, scores or measured distance |
| NIGHT-04 | Reported cardboard success | No independently matched recording, verified scores or measured distance |

These labels do not establish a complete trial denominator or four independent instrumented trials. Exact individual trial times, repetition counts, distances and power measurements are not supplied by the entries. Keep their recorded observations and blank fields unchanged. The [parts and findings](../FinalReportCode/PARTS_AND_FINDINGS.md) and [known issues](../FinalReportCode/KNOWN_ISSUES.md) place these observations in the last course implementation and its limits.

## October detector records

These sessions belong to the earlier grayscale/growth program and retain their original rule and measurements:

| Trial | Changed-region area | Frames | Recorded result |
|---|---|---|---|
| [Stationary object](captures/20261031-183457-917906-stationary-no-approach/index.html) | 16.250–16.375% | 10 | Large region without growth; no alarm |
| [Approaching object](captures/20261031-183551-894064-approaching-growth-test/index.html) | 15.000–32.646% | 5, then 10 empty-scene frames | Alarm on the fifth growing frame; the empty follow-up was rejected |
| [Centered small-object repeat](captures/20261031-183751-692936-centered-small-target-repeat/index.html) | 3.792–7.458% | 10 | No alarm under the 10% growth rule |

They are indoor surrogate observations, not current fusion performance measurements. The [earlier test history](HISTORY.md) preserves the full chronology, incomplete recordings and other results: the 3%/5% size-only stages, false alarms, [sound/RGB trial](captures/20261031-163535-273574-final-rgb-large-target/index.html), [camera diagnostic](captures/20261031-180337-326915-d12-camera-diagnostic/index.html) and [growth startup](captures/20261031-183354-551487-approach-10-percent-startup/index.html). `CAMERA_TEST` zero-area values are diagnostic placeholders.

The [classifier experiment](../experiments/deer-classifier/README.md) and its score-only test files are a separate earlier path. Their results are not the decision mechanism used by the current ground detector.

## New recordings and checks

The [runbook](../FinalReportCode/RUNBOOK.md#record-a-controlled-session) and [recording tools guide](../tools/README.md) describe new raw-byte capture, event/score association, provenance and host tests. Host tests check recording behavior with retained or constructed inputs; they do not replay the current image algorithm or verify hardware.

For future observations, record actual conditions, settings, targets, distances and failures in a new log. The [preserved outdoor log](../FinalReportCode/OUTDOOR_TEST_LOG.csv) supplies the existing columns and four November accounts; keep its observations and unmeasured fields unchanged. Store new analysis or regenerated presentation separately from the original evidence.
