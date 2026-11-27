# Build, operate and record the main board

The integrated target is `vibration_fusion` in [firmware/motion-size](../firmware/motion-size/README.md). Its named environment selects the PIR/vibration/current image path. The program's [target table](../firmware/motion-size/README.md#environments) describes the six alternatives; `classifier_test` is the retained growth alternative, not the fusion target.

The preserved [November 23 account](CURRENT_STATE_2026-11-23.md) records the configuration and observations from that session. Use the current build settings and recording commands below for this checkout; the dated account remains unchanged.

## Build the integrated target

Use PlatformIO Core. From the repository root:

```sh
pio run --project-dir deer_deterrent/firmware/motion-size --environment vibration_fusion
```

The project pins espressif32 6.11.0 and the ESP-IDF framework package 3.50402.0; the component manifest pins ESP-DL 3.3.14 and esp32-camera 2.1.3. CMake is constrained to the 3.30 patch family. See [platformio.ini](../firmware/motion-size/platformio.ini), [the component manifest](../firmware/motion-size/src/idf_component.yml) and [the lock file](../firmware/motion-size/dependencies.lock) for the declared configuration. ESP-DL supplies the JPEG decoder used by this program.

Platform 6.11 supplies the Kconfig 2.5 Python tools during a fresh ESP-IDF bootstrap. The older 6.10 bootstrap's Kconfig 1.5 package failed configuration of this project with a `MenuNode.help` error. An existing Core directory can retain that older framework-specific Python environment, so use a new empty Core directory for a clean provisioning check and record the actual tool versions. The framework stays at ESP-IDF 5.4.2; the platform update does not select a different detector or board.

The project uses PlatformIO's native Core/package directories unless environment overrides are supplied. Build output defaults to `.pio/build-native/vibration_fusion` within the motion-size project. The framework and build paths must be free of spaces for the pinned ESP-IDF integration. Keep the explicit environment name when recording a build result; a generic successful build does not by itself identify the intended target.

### Existing Windows helper

From the repository root in PowerShell:

```powershell
Set-Location deer_deterrent/firmware/motion-size
.\build.ps1 -PioArgs @('-e','vibration_fusion')
```

The unchanged helper requires the project beneath the current Windows user profile. It checks or creates the `V:` alias, rejects conflicting use of that drive, sets the PlatformIO Core path to the alias and forwards the argument array. The package directory then defaults beneath that same Core path. The helper checks esp-idf-kconfig 2.5.4 when its IDF Python environment already exists and can install that version. First-use framework/tool provisioning is separate from selecting the correct program.

### Configuration and upload

PlatformIO selects `sdkconfig.<environment>`. Fusion starts from `sdkconfig.defaults` when no `sdkconfig.vibration_fusion` exists; the tracked `sdkconfig.pir_wifi_camera_test` belongs to that diagnostic. Existing generated configuration values can take precedence over later defaults, so record the actual selected configuration and tool versions with a build.

Compilation does not upload firmware. For an intended Windows upload through the same helper, add the upload target and the board's verified port:

```powershell
.\build.ps1 -PioArgs @('-e','vibration_fusion','-t','upload','--upload-port','COM5')
```

`COM5` is the port named in the preserved handoff and is only an example here. Use the actual device port and close other serial readers first. The equivalent direct PlatformIO command adds `--target upload --upload-port` and that port to the explicit fusion build command. Uploading a diagnostic replaces fusion until fusion is uploaded again. No upload is needed to inspect saved evidence or run the host recorder tests.

## Start fusion operation

Use the [source camera configuration](../firmware/motion-size/src/app_main.cpp), existing [camera/RGB pin map](../WIRING.md) and [dated hardware account](CURRENT_STATE_2026-11-23.md). The latter describes the separate PIR supply with common ground; the feeder sender source is not included here.

1. Fix the camera in place and keep the view empty through the eight-second settling interval and all twelve baseline frames. Reference pictures use the same white-light capture sequence as detection pictures.
2. Allow the sixty-second PIR warm-up. Read `DETECTION_MODE` after calibration to identify whether the reference enabled color assistance.
3. PIR LOW for 500 ms followed by HIGH for 100 ms opens a ten-second vibration wait. A fresh message during that wait starts capture. See the [message contract](../firmware/motion-size/VIBRATION_TEST.md).
4. Two consecutive frames qualifying through the 7% grayscale or dark-enabled 10% assisted route start the output cycle. A failed ten-frame burst has no timed post-miss pause; an output cycle is followed by a 4.5-second cooldown and fresh PIR rearming.

Reference mode remains fixed until recalibration/reset. Keep the original reference setup and actual scene conditions in the recording notes. `CAMERA_TEST`, `LARGE_CHANGE_TEST_ONLY`, SETTLING and CALIBRATING records have diagnostic/setup meanings; their values are not ordinary target-performance observations.

## Record a controlled session

Use Python 3.10 or newer and the serial dependency described in [tools/README.md](../tools/README.md). From `deer_deterrent`, with other serial readers closed:

```sh
python tools/record_photos.py --port COM5 --seconds 120 --label fusion-01
```

Choose the actual port. Recording uses 115200 baud. The example starts a new timestamped directory under `tools/captures`; `--output` can name another new directory. Start recording before the trigger when the complete PIR/wait/capture history matters. Use `--notes` for actual power, target, distance, illumination, reference and sender conditions.

The existing optional actions are explicit:

```sh
python tools/record_photos.py --port COM5 --seconds 120 --label new-reference --calibrate
python tools/record_photos.py --port COM5 --seconds 120 --label controlled-repeat --arm
```

`--calibrate` requests `BASELINE`: cancel current work, wait three seconds and learn twelve new empty frames. It selects color assistance again without restarting the original PIR warm-up clock. `--arm` requests `ARM`: cancel current work and rearm while retaining the reference; warm-up and the qualified LOW/HIGH sequence still apply. These options are mutually exclusive. Use no action flag when observing the automatic lifecycle, and mark any controlled reset deliberately. Cancelling an active output cycle still produces its completion handling and normal post-output cooldown.

A recorded host write is a request; the device's observed acknowledgement is separate. `--config-file` and `--firmware-binary` hash supplied local files, which does not prove those files were running on the board. The recorder adds no new board command.

Keep `serial.raw`, `events.jsonl`, the paired JPEG/JSON files, `summary.json`, `index.html` and `run_manifest.json` together. The tools guide explains schema-3 association, close status, errors and incomplete observations. A closed manifest or successful recorder exit establishes its defined recording result, not a successful detection or verified physical response. Keep new outputs separate from original sessions under `tests/captures`.

## Checks and interpretation

For host recording tests, from `deer_deterrent`:

```sh
python -I -B -m unittest discover -s tools -p 'test_*.py' -v
```

These check transport, event/score association and presentation with retained or constructed inputs. They require no board, model, Pillow or C++ compiler and do not establish camera decisions or physical output behavior.

For later device observations, record the selected environment and distinguish these cases:

| Case | What to observe |
|---|---|
| PIR without a notification | The wait opens and times out with the camera in standby |
| Notification without a qualified PIR window | Receipt may be acknowledged, but fusion does not start a camera burst |
| Qualified PIR plus a fresh notification | Camera start, every retained attempt/score and the resulting confirmed or rejected burst |
| A confirmed output followed by another attempt | Software ON/OFF, the configured cooldown and new LOW/HIGH rearm, with physical observations recorded separately |
| Dark targets at documented distances | Both score paths, reference mode and every failure as well as success; no replacement of a missing reference by an apparently empty operational image |

The [saved night run](../tests/README.md#november-23-fusion-session) contains a grayscale-qualified software alarm, not a color-only activation. Its original gallery retains a three-frame caption that does not describe this program. Preserve that evidence; use the current guides and recorded score/state context when interpreting it.
