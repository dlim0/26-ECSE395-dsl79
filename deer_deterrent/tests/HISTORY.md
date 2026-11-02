# Historical working notes

Chronological record copied before the November 1 handoff. Status and threshold statements below describe their own point in time; use README.md and the team handoff for current behavior.

---

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

## RGB revision — October 31

White capture light and 5 Hz alarm flashes added; TFT disabled. Historical captures above predate RGB. Verify white on all channels, learn a fresh empty reference, repeat small/large checks and confirm buzzer/light both stop. See firmware/motion-size/BUILD-STATUS.txt for build/upload status.

## Sound + RGB end-to-end check — October 31

Firmware reflashed successfully to COM5. Startup/reference learning completed without errors. [Saved test gallery](captures/20261031-163535-273574-final-rgb-large-target/index.html). One PIR event confirmed after changed areas 22.396%, 22.771%, 16.958%; one alarm ON/OFF pair. User confirmed three buzzer pulses plus white flashes and both stopping. Firmware returned to ARMED with zero cooldown, then accepted a second PIR event. Its ten-frame window lacked three consecutive large frames and entered 120-second cooldown without another alarm. No device/transfer errors.

Visual inspection shows a nearby hand/forearm, not a full-body deer/person: this verifies a large image-region trigger and actuation, not deer recognition. An initial frame arrived before the manual ARM reset and is not part of the two subsequent recorded bursts. The summary reports 13 measured frames for those bursts. No matched flash-off comparison was captured, so these photos do not establish the LED illumination gain.

## D12 camera diagnostic — October 31

After a reported loose Camera D3 → Feather D12/GPIO12 connection, camera_diagnostic was flashed to bypass PIR. Eight checksum-verified JPEGs arrived in 15 seconds without device/transport errors. Visual inspection confirms a recognizable indoor scene and nearby hand (camera rotated). [Gallery](captures/20261031-180337-326915-d12-camera-diagnostic/index.html). This confirms current capture/decoding/USB transfer, not PIR/detection operation. CAMERA_TEST area=0 values are placeholders; recorder summary counts must not be treated as detector results. Diagnostic firmware remains active, with buzzer disabled, until normal firmware is restored.

## Recorded large-hand repeat — October 31

[Gallery](captures/20261031-182520-584322-large-target-recorded-repeat/index.html). First burst: 28.604%, 28.146%, 27.792%; photo shows large hand/forearm and alarm activated/stopped. Three subsequent bursts also confirmed at roughly 5.4–5.8%; visually inspected frame 106 shows the apparently empty desk/keyboard. These later events are suspected false positives, not successful target trials. Four ON/OFF pairs total, 12 verified photos, no device/transport errors. Final state ARMED/PIR LOW. This exposes reference/lighting sensitivity near the 5% threshold and requires follow-up before claiming stable rejection.

## Approaching-target revision — October 31

New 10% floor plus five-frame growth gate replaces size-only confirmation. Embedded behavioral tests cover static/background growth rejection, retreat, single jump, undersized targets, noisy approach, unrelated-region/reset cases. Historical captures above predate these rules. Physical growing-target acceptance and static-scene rejection still need checking after flash. Build/upload status is in firmware/motion-size/BUILD-STATUS.txt.

Approach revision startup verification passed on COM5: embedded image/approach tests PASS, seven verified JPEGs, reference learned, no device/transport errors. [Startup gallery and event log](captures/20261031-183354-551487-approach-10-percent-startup/index.html). This validates startup and deterministic gate cases, not live detection performance. Physical approach/static checks remain pending.

## Physical 10% + growth comparison — October 31

| Trial | Retained measurements | Result |
|---|---|---|
| [Stationary large object](captures/20261031-183457-917906-stationary-no-approach/index.html) | Ten frames, 16.250–16.375%; object visible | WAITING_FOR_GROWTH throughout; no alarm; cooldown |
| [Approaching object](captures/20261031-183551-894064-approaching-growth-test/index.html) | 15.000 → 18.042 → 23.375 → 28.208 → 32.646% | Confirmed on fifth frame; one alarm ON/OFF; rearmed without cooldown. Subsequent empty ten-frame check at 0% entered cooldown without another alarm |
| [Small-change event](captures/20261031-183651-967957-small-target-growth-rule/index.html) | Ten frames, max 1.062% | No alarm; cooldown. Target mostly at image edge, so repeat centered for stronger small-target evidence |

These are indoor surrogate trials with a narrow object, not deer/bird recognition or field accuracy measurements. All three runs had no device/transport errors. Buzzer was previously disconnected; ON/OFF logs verify commands, not audible sound during these runs. Camera stayed fixed.

## Small-target repeat with visible object — October 31

[Saved gallery](captures/20261031-183751-692936-centered-small-target-repeat/index.html). PIR triggered one ten-frame burst. Areas: 4.333, 4.667, 5.146, 3.792, 5.333, 5.146, 4.854, 5.625, 7.104, 7.458%. No alarm; two-minute cooldown; no device/transport errors. Saved frame 70 visibly shows a small rectangular battery-like object at the left/lower part of the view. Although area increased overall, every frame remained below the 10% floor. This supports small foreground-change rejection in this scene; it is not a live bird trial.
