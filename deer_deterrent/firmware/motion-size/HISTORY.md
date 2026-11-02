# Historical working notes

Chronological record copied before the November 1 handoff. Status and threshold statements below describe their own point in time; use README.md and the team handoff for current behavior.

---

# Current approaching-target revision

The former 5%/three-frame size-only rule is replaced by 10% plus growth. Five frames must have spatially overlapping region boxes (intersection at least 30% of the smaller box between neighboring frames). The last three regions must each be ≥480 of 4,800 grid pixels (10%). Net growth must be ≥25% relative AND ≥96 grid pixels (two percentage points of the image), with at least two steps increasing by max(5 pixels, 5% of previous area). Regions smaller than 1% reset the track. Invalid capture, new PIR burst, manual ARM and BASELINE reset growth history.

These are heuristic starting thresholds. The largest component can change identity despite box overlap. Stationary, retreating or sideways-moving animals may be missed; a growing non-deer object can trigger. Small fluctuations are allowed. The ten-photo limit and prior alarm/cooldown rules remain.

Metadata includes cutoff_percent, growth_frames, growth_percent and growth_pixels plus rule constants. WAITING_FOR_GROWTH means large enough but not approach-confirmed. LARGE_CHANGE now means the growth gate passed. Startup runs embedded gate tests for static background, static large region, retreat, one-step jump, small growth, mildly noisy approach, unrelated regions and reset.

Build/upload normal firmware using `./build.ps1 -PioArgs @('-e','classifier_test','-t','upload','--upload-port','COM5')`. Keep the camera fixed and view empty during startup reference learning; wait for 60-second PIR warmup. Test by gradually moving a target closer across several frames, rather than putting a full-size target in view all at once.

The chronological 5% notes below describe earlier firmware and are superseded by this section.

---

# Current MVP â€” PIR-triggered size filter

ESP32-S3 TFT Feather + OV5640 + PIR GPIO5 + passive buzzer GPIO10. See [wiring](../../WIRING.md) and [test results](../../tests/README.md).

The camera learns 12 empty reference frames at startup after 8 seconds. Keep its view clear and mount fixed. PIR warmup lasts 60 seconds. A trigger wakes the camera and inspects up to ten frames. A largest changed region of at least 5% in three consecutive frames confirms a large target.

The buzzer gives three 1.5-second 2 kHz pulses with 0.5-second gaps. Confirmed targets have no timed cooldown: after the pattern finishes, PIR must return LOW and then HIGH to retrigger. An unconfirmed ten-frame window starts a 120-second cooldown. Camera errors abort and require a new PIR transition. The camera sleeps between checks; the processor remains awake. The TFT is disabled (CS HIGH, backlight LOW); Wi-Fi is disabled. RGB wiring: R=GPIO13/D13, G=GPIO36/SCK, B=GPIO35/MOSI, shared GND.

## Build

Install PlatformIO and place this folder under your Windows user profile. The helper uses V: as a space-free alias to that profile and the existing `.platformio` installation. It checks for conflicting V: use. From this directory in PowerShell:

```powershell
.uild.ps1
.uild.ps1 -PioArgs @('-t','upload','--upload-port','COM5')
```

COM5 is the previously observed port; check your current device port. Uploading replaces the running firmware. No upload is needed to read the saved report. Board/framework/component versions are pinned in platformio.ini and src/idf_component.yml. The current environment name `classifier_test` is retained for compatibility with sdkconfig and dependency settings; this project runs no recognition model. ESP-DL is retained for the JPEG decoding helper.

## Record a trial

Install `tools/requirements.txt` into the Python environment used for the recorder. Close other serial monitors, then from the package root:

```powershell
python tools/record_photos.py --port COM5 --seconds 45 --label large-target --arm
```

`--arm` clears cooldown and waits for PIR LOW then HIGH; it does not skip warmup. `--calibrate` relearns the empty scene. Output is saved under `tools/captures` by the copied recorder. JPEG integrity is checked by frame number, byte count and FNV-1a checksum. No photos are persisted on the Feather.

## Verification status

This RGB revision built and flashed successfully to COM5 on October 31. Reference calibration completed; user confirmed white capture flashes and TFT dark. Alarm flashes and small/large checks with the new lighting remain pending. The 5% phone/person result was demonstrated using an earlier one-second alarm. TFT readability is confirmed. The longer alarm and no-cooldown repeat-trigger behavior await physical confirmation. The review copy changes only build-path handling and documentation; the RGB revision changes application source.

## RGB capture and alarm light

White turns on at least 120 ms before each analyzed photo, including reference frames. Two queued frames are discarded, then a fresh image is acquired while white stays ON. Light turns off before processing. Pulse duration includes camera acquisition time; this is not a synchronized photographic strobe. Matching baseline/detection lighting reduces illumination changes, but physical testing is required.

Alarm: 5 Hz white flashes (100 ms on/off) during the 5.5-second buzzer pattern. Timer-driven flashes continue during USB transfers and turn off at the end or cancellation. Confirmed targets still have no timed cooldown; unconfirmed ten-frame windows pause two minutes. Never enable ENABLE_STATUS_TFT with RGB wired to the SPI pins.

## Standalone camera diagnostic

For a camera/D12 wiring check, explicitly select the diagnostic environment:

```powershell
.\build.ps1 -PioArgs @('-e','camera_diagnostic','-t','upload','--upload-port','COM5')
```

This build bypasses PIR and repeatedly captures/decode-checks 320x240 JPEGs with the white capture light. Buzzer stays silent. Camera D3 must connect to Feather D12/GPIO12. USB recorder saves CAMERA_TEST frames; area=0 is a placeholder, not a detection measurement. Valid JPEG decoding does not verify every wire by itself; inspect the saved image too.

Restore the normal PIR/size/light/buzzer firmware with:

```powershell
.\build.ps1 -PioArgs @('-e','classifier_test','-t','upload','--upload-port','COM5')
```

The default environment remains classifier_test. Diagnostic firmware stays active after its upload until normal firmware is restored.
