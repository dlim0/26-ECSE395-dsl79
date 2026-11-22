# Feeder vibration link

The main Feather creates the local Wi-Fi network `Feeder-Main` with bench password `FeederBench26`. Connect the feeder ESP32 Feather V2 as a Wi-Fi client. On each new vibration detection, send an HTTP POST to `http://192.168.4.1/vibration` with the exact nine-byte body `vibration` and no trailing newline. HTTP 200 with body `received` acknowledges delivery. Send once per detected event, rather than continuously while the sensor output is active.

- `vibration_receiver` verifies the radio and outputs. A fresh POST starts three 1.5-second 8 kHz pulses on GPIO10 with 0.5-second gaps and white RGB flashes. The camera stays in standby. Notifications received during a cycle are discarded.
- `vibration_fusion` is the integrated build. After baseline capture and PIR warmup, a LOW-to-HIGH transition on GPIO5 opens a 10-second vibration window with the camera in standby. A fresh vibration received during the window wakes the camera even if PIR has returned LOW. Earlier events are discarded when the window opens. A changed region of at least 10% qualifies within the burst. An expired window leaves the camera in standby until a new PIR trigger.

From a computer already connected to the Feeder-Main Wi-Fi network, simulate a vibration message in PowerShell:

```powershell
curl.exe --noproxy "*" --fail --data-binary vibration http://192.168.4.1/vibration
```

Use USB serial at 115200 baud to watch for `VIBRATION_RECEIVED`, `DETERRENT_ON` and `DETERRENT_OFF`.
