#include <Arduino.h>
// This is required in PlatformIO but hidden in the standard Arduino IDE.

#define LED_PIN 13

void setup() {
  pinMode(LED_PIN, OUTPUT);
  // TODO: Define your baud rates
  Serial.begin(115200); // Start the Serial connection
}

void loop() {
  // TODO: Define your text output
  Serial.println("LeBron Jamz"); // Print the words to the Serial Monitor.
  
  // TODO: Set up your delay in milliseconds
  digitalWrite(LED_PIN, HIGH); // LED On
  delay(500); // Speed in milliseconds
  digitalWrite(LED_PIN, LOW); // LED Off
  delay(100); // Speed in milliseconds
}
