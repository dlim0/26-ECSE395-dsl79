> **Current November 23 firmware and test status:** [Read the updated handoff](CURRENT_STATE_2026-11-23.md). The older descriptions below are historical and may describe the superseded growth-only detector.

# Build, run, record and recover

## Normal operation

1. Follow [WIRING.md](../WIRING.md). Camera D3 is Feather D12/GPIO12; PIR OUT is D5/GPIO5. Keep RGB wired to 13/SCK/MOSI only with TFT-disabled firmware.
2. Mount the camera before power-up. Keep the view empty during the initial 8-second wait and 12 reference frames. Every captured reference frame uses white illumination.
3. Allow 60-second PIR warmup (measured after camera initialization). Wait for PIR LOW, then move the target toward the camera over several frames.
4. Up to ten images are checked. Confirmed approach gives a 5.5-second alarm; both light and buzzer signal stop. Wait for PIR LOW before another HIGH. An unconfirmed window gives 120-second cooldown; if PIR remains HIGH at expiry it may start another check.

On battery, detection runs locally and USB photo transfer is skipped. Photos are not saved persistently on the Feather. A disconnected buzzer does not block detection or RGB; it simply makes the buzzer signal inaudible. The MCU remains awake between checks; camera standby is not full-system deep sleep.

## Windows build and flash

Install PlatformIO. Place the repository below your Windows user profile; the helper expects PlatformIO at `.platformio` under that profile and creates/reuses V: as its space-free alias. It stops on conflicting V: usage. A fresh machine may need PlatformIO/ESP-IDF dependency installation; the helper checks esp-idf-kconfig 2.5.4 once its IDF Python environment exists. Linux/macOS build-path settings are not supplied/tested here.

From `deer_deterrent/firmware/motion-size`:

```powershell
.uild.ps1 -PioArgs @('-e','classifier_test')
.uild.ps1 -PioArgs @('-e','classifier_test','-t','upload','--upload-port','COM5')
```

Check the actual device port; COM5 is the last observed value, not a guaranteed assignment. Close serial monitors before upload. No reflash is required just to clear cooldown or recalibrate. The environment's legacy name does not select the old deer model. Current dependencies: espressif32 6.10.0, ESP-IDF 5.4.2, camera 2.1.3, ESP-DL 3.3.14 (JPEG helper), CMake 3.30.2.

## USB photo recording

From `deer_deterrent`:

```powershell
python -m pip install -r tools/requirements.txt
python tools/record_photos.py --port COM5 --seconds 45 --label trial-01
python tools/record_photos.py --port COM5 --seconds 45 --label new-empty-reference --calibrate
python tools/record_photos.py --port COM5 --seconds 45 --label controlled-repeat --arm
python -m unittest discover -s tools -p test_transfer.py -v
```

`--calibrate` cancels the active window/alarm, clears cooldown, waits three seconds, and learns 12 new empty frames. `--arm` cancels active work and clears cooldown while preserving the reference; it does not bypass warmup and needs PIR LOW then HIGH. Use these separately (calibrate wins if both are provided). Only one serial monitor can hold the port.

Recorder output goes to `tools/captures/<timestamp>-<label>` (gitignored until deliberately copied into `tests/captures`). Keep all JPG, JSON, events.jsonl, summary.json and index.html files together. Originals are unchanged; galleries overlay region boxes. Recorder validates frame IDs, JPEG markers, byte length and FNV-1a transfer checksum. A completed summary's large_frames counts confirmed frames, not independent trials.

## Camera-only diagnostic and restore

```powershell
.uild.ps1 -PioArgs @('-e','camera_diagnostic','-t','upload','--upload-port','COM5')
```

This repeatedly captures with white illumination, regardless of PIR, with buzzer silent. Repeated flashes in this mode are expected. CAMERA_TEST area=0 is a placeholder, not a detection result. Inspect images as well as decode status.

Restore normal operation explicitly:

```powershell
.uild.ps1 -PioArgs @('-e','classifier_test','-t','upload','--upload-port','COM5')
```

Do not flash the archived Arduino/TFT prototype with RGB connected to the shared SPI pins. The separately archived classifier experiment also replaces normal operation when uploaded.
