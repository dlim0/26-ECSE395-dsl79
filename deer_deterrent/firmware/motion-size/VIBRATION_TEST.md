# Feeder vibration interface

The S3 main board creates the `Feeder-Main` Wi-Fi access point. Use the credentials configured in [src/vibration_receiver.hpp](src/vibration_receiver.hpp). The feeder-side board connects as a client and reports a new sensor event through the contract below. The [November 23 hardware account](../../FinalReportCode/CURRENT_STATE_2026-11-23.md) identifies a Feather V2 reading vibration DO on GPIO27; its sender firmware is not included in this repository.

## Message contract

| Field | Required value or behavior |
|---|---|
| Method and URL | HTTP POST to `http://192.168.4.1/vibration` on the main board's access point |
| Body | Exactly nine bytes: `vibration`, with no newline or additional data |
| Accepted response | HTTP 200, body `received` |
| Rejected body | HTTP 400 when the length or contents differ |
| Event lifetime | The main board timestamps receipt and consumes only an event no more than 2,000 ms old |
| Repeated notifications | Only the latest receipt is retained; this is not a queue of sensor events |

Send once per new vibration event rather than continuously while the sensor output remains active. An HTTP acknowledgement establishes receipt, not an image decision or output activation. The vibration event message carries no sender identity or independent proof that a physical sensor produced it.

## Select the target deliberately

**`vibration_fusion` is the default integrated program.** After reference learning and PIR warm-up, LOW for 500 ms followed by HIGH for 100 ms opens a ten-second window. Earlier notifications are discarded. A fresh notification consumed during the window starts up to ten camera-frame attempts, even if PIR has returned LOW. An expired window leaves the camera in standby and requires a new qualified PIR event.

The camera then uses the [current image rule](README.md#image-rule): grayscale region at least 7%, or a grayscale/color union at least 10% when calibration enabled color assistance. Two consecutive frames must qualify through either route before the automatic response starts. A notification alone does not satisfy that image rule.

**`vibration_receiver` is a separate link/output diagnostic.** A fresh notification directly starts three 1.5-second 8 kHz pulses with 0.5-second gaps and white flashing. The camera stays in standby, and notifications consumed during an active cycle are discarded. This target bypasses the PIR and image decisions; it does not verify the integrated sequence.

**`pir_wifi_camera_test` is a separate camera diagnostic with Wi-Fi active.** Qualified PIR starts capture without waiting for a notification. Its automatic response is suppressed. Select `vibration_fusion` again to restore the integrated program.

## Operator-run protocol check

From a computer already connected to the main board's access point, a PowerShell request can exercise the HTTP interface:

```powershell
curl.exe --noproxy '*' --fail --data-binary vibration http://192.168.4.1/vibration
```

On macOS/Linux, use the same arguments with `curl`. For fusion, first observe `WAIT_FOR_VIBRATION` and send within that window. Keep a [USB recording](../../FinalReportCode/RUNBOOK.md#record-a-controlled-session) at 115200 baud so the receipt, camera start, frame scores and output events can be interpreted together.

Check PIR-only and notification-only cases separately, then a combined case with a visible target and a complete output/cooldown/rearm cycle. Record the selected environment and actual conditions. A receiver-only output response or a successful HTTP status does not establish fusion behavior, sender sensing performance or deterrence effectiveness.
