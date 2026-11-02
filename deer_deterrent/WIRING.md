# Working wiring — Adafruit ESP32-S3 TFT Feather

MCU GPIO numbers and Feather labels differ. This is the working mapping copied from the tested firmware.

| OV5640 label | Feather label | GPIO |
|---|---|---:|
| 3V | 3V | Power |
| G | GND | Ground |
| SDA | TX | 1 |
| SCL | SCL | 41 |
| HS | A0 | 18 |
| XC | A1 | 17 |
| D8 | A2 | 16 |
| D6 | A3 | 15 |
| D4 | A4 | 14 |
| D2 | A5 | 8 |
| VS | RX | 2 |
| PC | SDA | 42 |
| D9 | D6 | 6 |
| D7 | D9 | 9 |
| D5 | D11 | 11 |
| D3 | D12 | 12 |
| PD | MISO | 37 |
| RT | Unconnected | -1 |

PIR OUT → D5/GPIO5; shared ground. Preserve the existing tested PIR supply arrangement; user confirmed operation with their battery setup. Buzzer I/O → D10/GPIO10, VCC → 3V, GND → shared ground.

## RGB wiring (TFT disabled)

| Module | Feather | GPIO |
|---|---|---:|
| R | D13 | 13 |
| G | SCK | 36 |
| B | MOSI | 35 |
| GND | Shared GND | Ground |

New firmware skips TFT initialization, holds TFT CS7 HIGH and backlight45 LOW. GPIO21 remains enabled. Camera/PIR/buzzer wiring is unchanged. Do not enable TFT code while the RGB uses its SPI pins.
