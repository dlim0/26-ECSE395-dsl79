//dsl79: extrapolated most of the logic for the code from the video
#include <Arduino.h>

// dsl79: Connect the touch sensor's digital output to GPIO 34.
const int sensorPin = 34;

// dsl79: Use GPIO 13 for the onboard LED.
const int ledPin = 13;

void setup() {
    // dsl79: Start serial communication at 115200 baud.
    Serial.begin(115200);

    // dsl79: Configure GPIO 34 to read the touch sensor's output.
    pinMode(sensorPin, INPUT);

    // dsl79: Configure the onboard LED pin as an output.
    pinMode(ledPin, OUTPUT);
}

void loop() {
    // dsl79: Read whether the sensor's digital output is HIGH or LOW.
    int sensorValue = digitalRead(sensorPin);

    // dsl79: A HIGH signal indicates touch for an active-HIGH sensor.
    if (sensorValue == HIGH) {
        // dsl79: Display a message when touch is detected.
        Serial.println("Touch detected!");

        // dsl79: Turn on the onboard LED.
        digitalWrite(ledPin, HIGH);
    }
    else {
        // dsl79: Display a message when no touch is detected.
        Serial.println("No touch detected...");

        // dsl79: Turn off the onboard LED.
        digitalWrite(ledPin, LOW);
    }

    delay(50);
}