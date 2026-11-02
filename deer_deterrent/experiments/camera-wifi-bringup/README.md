# Historical Wi-Fi camera/PIR burst prototype

Archived Arduino stage from the standalone OV5640 Camera Test workspace. This produced camera images over the Feather's local Wi-Fi access point, then added PIR-gated bursts. It is preserved to explain camera bring-up; the current growth detector is [firmware/motion-size](../../firmware/motion-size/README.md).

`src/main.cpp`, `include/camera_pins.h` and `platformio.ini` preserve the historical code/configuration. The old demo access-point password was replaced by `ChangeMe123`; set a local test password before use. This firmware uses TFT/SPI and does not contain the current RGB/growth algorithm. Do not flash it with RGB wired to the TFT SPI pins. No rebuild/flash of this archived project was performed for the November 1 handoff.

The historical AP is `Feather-Camera-Test`; the local camera page was at 192.168.4.1. Current normal firmware has Wi-Fi off, and saved galleries work without the device. Use the current [wiring](../../WIRING.md), not an older prototype diagram, when assembling the current MVP.
