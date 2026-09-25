#include <Arduino.h>

constexpr uint8_t PIR_PIN = 14; // feather pin 14
constexpr uint8_t BUZZER_PIN = 27; // feather pin 27
constexpr unsigned int BUZZER_FREQUENCY_HZ = 2000; // pitch of buzzer in Hz
constexpr unsigned long PIR_WARMUP_MS = 60000; // 60000ms = 60s

bool motionPreviouslyDetected = false;

void setup() {
  Serial.begin(115200);
  pinMode(PIR_PIN, INPUT); // Set the PIR pin as input
  pinMode(BUZZER_PIN, OUTPUT); // Set the buzzer pin as output
  digitalWrite(BUZZER_PIN, LOW);

  Serial.println("PIR warming up for 60 seconds. Buzzer stays off.");
  // According to the datasheet PIR initializes for 60s and before that time it could cause false positives/
  delay(PIR_WARMUP_MS); // warmup is 60s
  Serial.println("Ready. Waiting for motion...");
}

void loop() {
  const bool motionDetected = digitalRead(PIR_PIN) == HIGH;

  // Only change the tone and print a message when the sensor changes state.
  if (motionDetected != motionPreviouslyDetected) {
    if (motionDetected) {
      tone(BUZZER_PIN, BUZZER_FREQUENCY_HZ); // Tone triggers depending on the if statement and is telling buzzer pin to run the freqeuncy
      Serial.println("Motion detected: buzzer ON.");
    } else {
      noTone(BUZZER_PIN); // noTone stops the buzzer from running
      Serial.println("PIR output LOW: buzzer OFF.");
    }
    motionPreviouslyDetected = motionDetected;
  }

  delay(20);
}
