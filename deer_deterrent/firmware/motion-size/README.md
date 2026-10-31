# Current MVP â€” PIR-triggered size filter

ESP32-S3 TFT Feather + OV5640 + PIR GPIO5 + passive buzzer GPIO10. See [wiring](../../WIRING.md) and [test results](../../tests/README.md).

The camera learns 12 empty reference frames at startup after 8 seconds. Keep its view clear and mount fixed. PIR warmup lasts 60 seconds. A trigger wakes the camera and inspects up to ten frames. A largest changed region of at least 5% in three consecutive frames confirms a large target.

The buzzer gives three 1.5-second 2 kHz pulses with 0.5-second gaps. Confirmed targets have no timed cooldown: after the pattern finishes, PIR must return LOW and then HIGH to retrigger. An unconfirmed ten-frame window starts a 120-second cooldown. Camera errors abort and require a new PIR transition. The camera sleeps between checks; the processor remains awake. TFT backlight is enabled for testing; Wi-Fi is disabled.

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

The source in this folder matches the last successfully flashed working source. The 5% phone/person result was demonstrated using an earlier one-second alarm. TFT readability is confirmed. The longer alarm and no-cooldown repeat-trigger behavior await physical confirmation. The review copy changes only build-path handling and documentation; the copied application source is unchanged.
