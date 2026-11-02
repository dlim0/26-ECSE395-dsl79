#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include "esp_camera.h"
#include "camera_pins.h"

constexpr uint8_t PIR_PIN = 5;
constexpr uint8_t BUZZER_PIN = 10;
constexpr unsigned long PIR_WARMUP_MS = 60000;
constexpr char AP_NAME[] = "Feather-Camera-Test";
constexpr char AP_PASSWORD[] = "ChangeMe123";
WebServer server(80);
Adafruit_ST7789 display(TFT_CS, TFT_DC, TFT_RST);
uint8_t* latestImage = nullptr;
size_t latestLength = 0;
unsigned long captureCount = 0;
unsigned long warmupStart = 0;
unsigned long lastCountdown = 999;
bool pirReady = false;
bool previousPir = false;
String statusText = "PIR warming up";
String lastSource = "none";
constexpr unsigned MAX_BURST_PHOTOS = 10;
constexpr unsigned long SHOT_GAP_MS = 2000;
constexpr unsigned long COOLDOWN_MS = 120000;
struct SavedPhoto { uint8_t* data; size_t length; unsigned long id; };
SavedPhoto burstPhotos[MAX_BURST_PHOTOS] = {};
unsigned savedCount = 0;
unsigned attemptCount = 0;
unsigned long burstId = 0;
unsigned long nextShotAt = 0;
unsigned long cooldownStart = 0;
bool burstActive = false;
bool coolingDown = false;
bool deerDetected = false;
String bootId;

bool reached(unsigned long now, unsigned long deadline) {
  return static_cast<int32_t>(now - deadline) >= 0;
}

void beginBurst(const char* source) {
  for (auto& photo : burstPhotos) {
    free(photo.data);
    photo = {};
  }
  latestImage = nullptr;
  latestLength = 0;
  savedCount = 0;
  attemptCount = 0;
  deerDetected = false;
  coolingDown = false;
  burstActive = true;
  ++burstId;
  lastSource = source;
  nextShotAt = millis();
}

void showStatus(const String& text) {
  statusText = text;
  display.fillScreen(ST77XX_BLACK);
  display.setTextWrap(true);
  display.setTextColor(ST77XX_WHITE);
  display.setTextSize(2);
  display.setCursor(4, 4);
  display.println("PIR Burst V4");
  display.setTextSize(1);
  display.println();
  display.println(text);
  display.printf("\nPhotos: %lu\n", captureCount);
  display.println("Camera standby between shots");
  display.println("192.168.4.1 | Buzzer OFF");
  Serial.println(text);
}

void standbyCamera() {
  pinMode(CAM_PWDN, OUTPUT);
  digitalWrite(CAM_PWDN, HIGH);
}

bool startCamera() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = CAM_D0; c.pin_d1 = CAM_D1;
  c.pin_d2 = CAM_D2; c.pin_d3 = CAM_D3;
  c.pin_d4 = CAM_D4; c.pin_d5 = CAM_D5;
  c.pin_d6 = CAM_D6; c.pin_d7 = CAM_D7;
  c.pin_xclk = CAM_XCLK;
  c.pin_pclk = CAM_PCLK;
  c.pin_vsync = CAM_VSYNC;
  c.pin_href = CAM_HREF;
  c.pin_sccb_sda = CAM_SDA;
  c.pin_sccb_scl = CAM_SCL;
  c.pin_pwdn = CAM_PWDN;
  c.pin_reset = CAM_RESET;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_QVGA;
  c.jpeg_quality = 12;
  c.fb_count = 1;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  const esp_err_t error = esp_camera_init(&c);
  if (error != ESP_OK) {
    standbyCamera();
    showStatus("Camera init failed: " + String(esp_err_to_name(error)));
    return false;
  }
  return true;
}

bool takePhoto(const char* source) {
  showStatus(String(source) + ": waking camera...");
  if (!psramFound()) {
    showStatus("PSRAM missing. Capture unavailable.");
    return false;
  }
  if (!startCamera()) return false;
  // Reinitialize after power-down and allow exposure/white balance to settle.
  // Wi-Fi remains connected; requests wait until this short capture finishes.
  delay(1200);
  for (int i = 0; i < 3; ++i) {
    camera_fb_t* discard = esp_camera_fb_get();
    if (discard) esp_camera_fb_return(discard);
    delay(80);
  }
  camera_fb_t* frame = esp_camera_fb_get();
  bool success = false;
  String error = "Capture failed; previous photo retained.";
  if (frame) {
    if (frame->format == PIXFORMAT_JPEG && frame->len >= 4 &&
        frame->buf[0] == 0xff && frame->buf[1] == 0xd8 &&
        frame->buf[frame->len - 2] == 0xff && frame->buf[frame->len - 1] == 0xd9) {
      uint8_t* copy = static_cast<uint8_t*>(ps_malloc(frame->len));
      if (copy) {
        memcpy(copy, frame->buf, frame->len);
        latestImage = copy;
        latestLength = frame->len;
        ++captureCount;
        burstPhotos[savedCount++] = {copy, frame->len, captureCount};
        lastSource = source;
        success = true;
        Serial.printf("Saved JPEG %lu: %u bytes\n", captureCount, unsigned(latestLength));
      } else error = "Not enough memory; previous photo retained.";
    } else error = "Invalid JPEG; check camera data wiring.";
    esp_camera_fb_return(frame);
  }
  esp_camera_deinit();
  standbyCamera();
  showStatus(success ? "Burst photo " + String(savedCount) + "/10 saved. Waiting for classifier."
                     : error);
  return success;
}

void sendLatest() {
  uint8_t* image = latestImage;
  size_t length = latestLength;
  if (server.hasArg("id")) {
    image = nullptr;
    length = 0;
    const String requestedId = server.arg("id");
    for (const auto& photo : burstPhotos) {
      if (photo.data && requestedId == String(photo.id)) {
        image = photo.data;
        length = photo.length;
        break;
      }
    }
  }
  if (!image) {
    server.send(404, "text/plain", "No photo yet. Wait for PIR warmup and trigger motion, or use Capture now.");
    return;
  }
  server.sendHeader("Cache-Control", "no-store");
  if (server.hasArg("download"))
    server.sendHeader("Content-Disposition", "attachment; filename=pir-capture.jpg");
  server.setContentLength(length);
  server.send(200, "image/jpeg", "");
  WiFiClient client = server.client();
  size_t sent = 0;
  const unsigned long start = millis();
  while (sent < length && client.connected() && millis() - start < 10000) {
    const size_t remaining = length - sent;
    const size_t written = client.write(image + sent, remaining > 4096 ? 4096 : remaining);
    if (!written) break;
    sent += written;
    delay(0);
  }
}

void setup() {
  Serial.begin(115200);
  bootId = String(esp_random(), HEX) + String(esp_random(), HEX);
  pinMode(PIR_PIN, INPUT_PULLDOWN);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  standbyCamera();
  pinMode(TFT_I2C_POWER, OUTPUT);
  digitalWrite(TFT_I2C_POWER, HIGH);
  pinMode(TFT_BACKLITE, OUTPUT);
  digitalWrite(TFT_BACKLITE, HIGH);
  delay(10);
  display.init(135, 240);
  display.setRotation(3);
  WiFi.mode(WIFI_AP);
  if (!WiFi.softAP(AP_NAME, AP_PASSWORD)) {
    showStatus("Wi-Fi startup failed. Reset to retry.");
    while (true) delay(1000);
  }
  server.on("/", HTTP_GET, []() {
    server.send(200, "text/html", R"HTML(<!doctype html><html><meta name="viewport" content="width=device-width"><title>PIR camera</title><body>
<h1>PIR burst camera test</h1><p id="status">Loading status...</p>
<button onclick="snap()">Start 10-photo burst</button> <a href="/latest.jpg?download=1">Download latest photo</a>
<p><img id="photo" style="max-width:100%" alt="Waiting for first photo"></p>
<p>Up to 10 photos per burst, stopping if the computer reports deer. Two-minute capture pause if PIR is still HIGH after 10 attempts. Camera standby between shots; Wi-Fi stays on. Buzzer OFF. Classifier must run separately on the computer.</p><p><a href="/burst">Burst photo manifest</a></p>
<script>let seen=0,busy=false;async function poll(){if(busy)return;try{let s=await(await fetch('/status',{cache:'no-store'})).json();document.getElementById('status').textContent=s.state+' | PIR '+(s.pir?'HIGH':'LOW')+' | Photos '+s.photos;if(s.photos&&s.photos!==seen){seen=s.photos;document.getElementById('photo').src='/latest.jpg?t='+Date.now()}}catch(e){document.getElementById('status').textContent='Reconnecting...'}}async function snap(){busy=true;try{let r=await fetch('/capture',{method:'POST'});if(!r.ok)alert(await r.text())}catch(e){alert('Capture request failed')}finally{busy=false;poll()}}setInterval(poll,1500);poll();</script></body></html>)HTML");
  });
  server.on("/status", HTTP_GET, []() {
    // Only fixed program messages enter this JSON field.
    String text = statusText;
    text.replace("\\", "\\\\"); text.replace("\"", "\\\""); text.replace("\n", "\\n");
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", "{\"state\":\"" + text + "\",\"pir\":" +
                String(digitalRead(PIR_PIN) == HIGH ? "true" : "false") +
                ",\"photos\":" + String(captureCount) +
                ",\"boot\":\"" + bootId + "\",\"burst\":" + String(burstId) +
                ",\"burst_active\":" + String(burstActive ? "true" : "false") +
                ",\"attempts\":" + String(attemptCount) +
                ",\"deer\":" + String(deerDetected ? "true" : "false") +
                ",\"cooldown_seconds\":" + String(coolingDown ? (COOLDOWN_MS - min(COOLDOWN_MS, millis() - cooldownStart) + 999) / 1000 : 0) + "}");
  });
  server.on("/capture", HTTP_POST, []() {
    if (burstActive || coolingDown || !pirReady) {
      server.send(409, "text/plain", "Wait for PIR warmup, active burst or cooldown to finish.");
      return;
    }
    beginBurst("Manual");
    showStatus("Manual burst started.");
    server.send(202, "text/plain", statusText);
  });
  server.on("/capture", HTTP_GET, []() {
    server.send(405, "text/plain", "Open / and use Capture now. Latest photo: /latest.jpg");
  });
  server.on("/latest.jpg", HTTP_GET, sendLatest);
  server.on("/photo.jpg", HTTP_GET, sendLatest);
  server.on("/burst", HTTP_GET, []() {
    String body = "{\"boot\":\"" + bootId + "\",\"burst\":" + String(burstId) + ",\"images\":[";
    for (unsigned i = 0; i < savedCount; ++i) {
      if (i) body += ',';
      body += "{\"id\":" + String(burstPhotos[i].id) + ",\"url\":\"/photo.jpg?id=" + String(burstPhotos[i].id) + "\"}";
    }
    server.sendHeader("Cache-Control", "no-store");
    server.send(200, "application/json", body + "]}");
  });
  server.on("/classification", HTTP_POST, []() {
    // Form fields bind each result to an actual retained photo and this boot/burst.
    if (server.arg("boot") != bootId || server.arg("burst") != String(burstId)) {
      server.send(409, "text/plain", "Stale boot or burst result.");
      return;
    }
    bool validPhoto = false;
    for (unsigned i = 0; i < savedCount; ++i)
      if (server.arg("id") == String(burstPhotos[i].id)) validPhoto = true;
    const String verdict = server.arg("deer");
    if (!validPhoto || (verdict != "true" && verdict != "false")) {
      server.send(400, "text/plain", "Expected retained photo id and deer=true or deer=false.");
      return;
    }
    if (verdict == "true" && !deerDetected) {
      deerDetected = true;
      burstActive = false;
      coolingDown = false;
      previousPir = true; // Require a LOW before another automatic rising edge.
      standbyCamera();
      showStatus("DEER reported by computer. Burst stopped; buzzer OFF.");
    }
    server.send(200, "text/plain", "Classification accepted.");
  });
  server.begin();
  warmupStart = millis();
  showStatus("PIR warming up: 60 seconds. Camera in standby.");
}

void loop() {
  server.handleClient();
  const unsigned long elapsed = millis() - warmupStart;
  if (!pirReady) {
    if (elapsed >= PIR_WARMUP_MS) {
      pirReady = true;
      previousPir = digitalRead(PIR_PIN) == HIGH;
      showStatus(previousPir ? "PIR HIGH at warmup end. Waiting for LOW, then motion."
                             : "Armed. Waiting for motion. Camera in standby.");
    } else {
      const unsigned long remaining = (PIR_WARMUP_MS - elapsed + 999) / 1000;
      if (remaining != lastCountdown) {
        lastCountdown = remaining;
        showStatus("PIR warming up: " + String(remaining) + " seconds.");
      }
    }
  } else if (burstActive) {
    if (reached(millis(), nextShotAt)) {
      ++attemptCount;
      const bool ok = takePhoto(lastSource.c_str());
      nextShotAt = millis() + SHOT_GAP_MS;
      if (!ok || attemptCount >= MAX_BURST_PHOTOS) {
        burstActive = false;
        previousPir = true;
        if (!ok || digitalRead(PIR_PIN) == HIGH) {
          coolingDown = true;
          cooldownStart = millis();
          showStatus(ok ? "10 shots attempted; PIR HIGH. Paused for 120 seconds."
                        : "Capture error. Paused for 120 seconds; check wiring/power.");
        } else {
          showStatus("Burst complete. Camera standby; waiting for next motion.");
        }
      }
    }
  } else if (coolingDown) {
    if (millis() - cooldownStart >= COOLDOWN_MS) {
      coolingDown = false;
      if (digitalRead(PIR_PIN) == HIGH) {
        beginBurst("PIR retry");
        showStatus("Cooldown ended; PIR HIGH. Starting new burst.");
      } else {
        previousPir = false;
        showStatus("Cooldown ended. Armed for motion.");
      }
    }
  } else {
    const bool high = digitalRead(PIR_PIN) == HIGH;
    if (high && !previousPir) {
      previousPir = true;
      beginBurst("PIR");
      showStatus("PIR motion: starting up to 10 photos.");
    } else if (!high && previousPir) {
      previousPir = false;
      showStatus("PIR LOW. Armed for next motion. Camera in standby.");
    }
  }
  delay(5);
}
