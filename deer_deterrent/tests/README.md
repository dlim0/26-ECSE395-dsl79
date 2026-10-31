# Saved test sequence — October 29, 2026

Open [index.html](index.html) locally for a directory of the original photo galleries. All sessions retain their original JPEGs, metadata and event logs. These are indoor surrogate tests with a fixed camera and unmeasured target distance.

| Step | Observation | Gallery/evidence |
|---|---|---|
| Empty view, initial 3% filter | 45 measured frames; max 0.000%; no large frames | [Default view](captures/20261029-162748-872374-default-view/index.html) |
| Phone as small target, 3% | 85 measured frames; max 1.896%; no large frames | [Small phone](captures/20261029-162902-877406-small-phone/index.html) |
| Person as large target, 3% | 84 valid measured frames; max 54.375%; 68 large frames | [Large person](captures/20261029-163019-306672-large-person/index.html) |
| PIR + mixed phone/forearm, 3% | ~7.8% changed region triggered the alarm; forearm means this was not a phone-only test | [Mixed target](captures/20261029-164009-749997-phone-deterrent/index.html) |
| Phone, revised 5% cutoff | Four retained frames: 0.979%, 2.812%, 2.167%, 1.771%; no alarm | [Phone](captures/20261029-164408-046795-five-percent-live/index.html) |
| Phone follow-up | Completed cooldown with lifetime alarm count 0 | [Status](captures/20261029-164500-946892-five-percent-window-end/summary.json) |
| Person, 5% cutoff | 11.250%, 11.208%, 8.417%; confirmation → buzzer ON → OFF; user heard it stop | [Person](captures/20261029-164554-843353-person-five-percent/index.html) |
| TFT startup and armed checks | Reference learning/warmup observed; armed standby; user confirmed readable display | [Startup](captures/20261029-180609-968612-display-startup/index.html), [armed status](captures/20261029-180701-165773-display-armed-check/summary.json) |

The initial person run excluded one malformed measurement; its 12 saved JPEGs passed integrity checks. The 5% phone recording ended mid-window, so only four measurements were retained; follow-up supports no alarm through completion, not a maximum for unseen frames. The 5% person log contains two OFF messages and one ON event; that is not two alarm cycles.

## Firmware version context

The final phone/person comparison used a one-second alarm and a cooldown after all completed windows. Current source subsequently changed to three 1.5-second pulses and no timed cooldown for confirmed targets. Both revisions built/flashed successfully. TFT readability is confirmed; the new alarm pattern and repeated confirmed-target behavior still need physical testing.

## Next checks

- Two large-target events separated by PIR LOW: both should trigger without a two-minute wait.
- One complete small-only ten-frame window: no alarm, then two-minute cooldown.
- Repeat at measured distances and outdoors. Apparent image size is not physical animal size; people, shadows, foliage or camera motion can trigger changes.

A phone is not an actual bird, and a person is not a deer. These tests demonstrate one indoor size-separation example, not field accuracy or deterrence effectiveness. User confirmed PIR operation with the tested battery setup; battery current/runtime are unmeasured.
