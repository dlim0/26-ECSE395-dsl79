#pragma once

// Layout V2: camera header rows grouped by Feather side.
// Use the V2 wiring table in README.md. This differs from the original upload.
constexpr bool CAMERA_BREAKOUT_CONFIRMED = true;

// Camera D2 is driver d0, not Feather GPIO 2.
constexpr int CAM_D0 = 8;  // Camera D2 -> Feather A5
constexpr int CAM_D1 = 12; // Camera D3 -> Feather 12
constexpr int CAM_D2 = 14; // Camera D4 -> Feather A4
constexpr int CAM_D3 = 11; // Camera D5 -> Feather 11
constexpr int CAM_D4 = 15; // Camera D6 -> Feather A3
constexpr int CAM_D5 = 9;  // Camera D7 -> Feather 9
constexpr int CAM_D6 = 16; // Camera D8 -> Feather A2
constexpr int CAM_D7 = 6;  // Camera D9 -> Feather 6
constexpr int CAM_XCLK = 17; // Camera XC -> Feather A1 (EXT clock jumper)
constexpr int CAM_PCLK = 42; // Camera PC -> Feather pad labeled SDA
constexpr int CAM_VSYNC = 2; // Camera VS -> Feather RX (one row-group exception)
constexpr int CAM_HREF = 18; // Camera HS -> Feather A0
constexpr int CAM_SDA = 1;   // Camera SDA -> Feather TX (software-selected SCCB data)
constexpr int CAM_SCL = 41;  // Camera SCL -> Feather SCL
constexpr int CAM_RESET = -1;
constexpr int CAM_PWDN = 37;
