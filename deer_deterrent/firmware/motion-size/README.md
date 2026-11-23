> **Current November 23 firmware and test status:** [Read the updated handoff](../../handoff/CURRENT_STATE_2026-11-23.md). The older descriptions below are historical and may describe the superseded growth-only detector.

# Current firmware: approaching foreground region

ESP32-S3 TFT Feather, OV5640, HC-SR501 PIR, common-ground RGB module, optional passive buzzer. [Team runbook](../../handoff/RUNBOOK.md) contains build/flash/record commands; [wiring](../../WIRING.md) is authoritative. The default normal environment is `classifier_test`; diagnostic is `camera_diagnostic`.

## Exact current gate

1. PIR LOW-to-HIGH wakes the camera after startup warmup and outside cooldown/alarm. Camera exposure settles before checking up to ten frames.
2. Decode 320x240 JPEG. Average 4x4 pixels into 80x60 grayscale, compensate median brightness shift, threshold differences at 25 grayscale levels, majority-filter 3x3 (at least five marked neighbors), then find the largest four-connected changed region.
3. Keep five associated region frames. Neighboring boxes must overlap by at least 30% of the smaller box. A region below 48 pixels (1%) resets tracking. This is spatial association, not semantic identity.
4. Last three areas must each be at least 480/4800 pixels (10%). Net increase from the first to fifth must be at least 25% relative AND at least 96 pixels (two percentage points of full image area).
5. At least two individual increases must be at least max(5 pixels, integer previous area/20). Small intervening fluctuations are allowed. A single size jump or steady large object does not suffice.

Confirmation keeps the logged state name LARGE_CHANGE. A sufficiently large but unconfirmed region is WAITING_FOR_GROWTH. Metadata includes cutoff, window, required growth, absolute gain, measured growth, region box and transfer checksums. Window history resets at new bursts, manual rearm/recalibration and capture/decode errors.

## Capture light, alarm and cooldown

White turns on for at least 120 ms before capture; two queued frames are discarded, a fresh JPEG is acquired while white remains on, then light turns off. Reference and detection captures use the same process. Duration includes camera acquisition time; this is not a synchronized camera strobe.

Alarm: three 1.5-second 2 kHz buzzer pulses with 0.5-second gaps, plus 5 Hz white flashes throughout 5.5 seconds. The timer task turns both signals off independently of USB photo streaming. After confirmation there is no timed cooldown: alarm finishes, then PIR must go LOW before a fresh HIGH. An unconfirmed ten-frame window has 120-second cooldown; still-HIGH PIR at expiry may start a new window. Camera errors abort without timed cooldown and require a fresh PIR transition.

White RGB uses R13/G36/B35. TFT disabled with CS7 high/backlight45 low; do not enable ENABLE_STATUS_TFT while those RGB connections remain. Camera standby between checks, MCU awake, Wi-Fi off. No persistent on-device photo storage.

## Verification

Last normal firmware flashed October 31. Embedded motion and approach selftests passed on-device; startup photos/reference learning passed; USB transfer unit tests passed. Physical recorded comparison: stationary ~16.3% object rejected; approaching object 15.0->32.646% confirmed on fifth frame, alarm commanded then stopped; small visible object max7.458% rejected. These are indoor surrogate examples, not field accuracy. User confirmed battery-only operation; runtime not measured. See [tests](../../tests/README.md).

The legacy [HISTORY.md](HISTORY.md) and [BUILD-STATUS.txt](BUILD-STATUS.txt) preserve earlier chronological status. No new firmware upload was done as part of the November 1 documentation handoff.
