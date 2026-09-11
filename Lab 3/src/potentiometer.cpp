/* //dsl79 
#include <Arduino.h>

//Put your potentiometer pin assignment here
// dsl79: using GPIO 34 as a connection
const int sensorPin = 34;

void setup() {
  // dsl79: Start serial communication at 115200 baud.
  Serial.begin(115200);
}

void loop() {
  //This line should print out the values from the sensor by Serial.println(??);
  //dsl79: using GPIO34 we connect to the potentiometer for the integer that the println is going to read out
  const int sensorPin = 34;
  //dsl79: the analogRead prints what the sensorPin is sending out
  Serial.println(analogRead(sensorPin));
  delay(50); 
}
  */