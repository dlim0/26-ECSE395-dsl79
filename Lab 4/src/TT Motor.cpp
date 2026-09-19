#include <Arduino.h>

// CHANGED: Example Feather V2 GPIOs: A1=25, A0=26. Match your wiring.
const int MOTOR_B_1A = 25;
const int MOTOR_B_1B = 26;
// CHANGED: Experiment settings. Swap power values to reverse direction.

void setup() {
  Serial.begin(115200); // CHANGED: Added status messages.

  pinMode(MOTOR_B_1A, OUTPUT);
  pinMode(MOTOR_B_1B, OUTPUT);

  analogWrite(MOTOR_B_1A, 0);
  analogWrite(MOTOR_B_1B, 0);

  Serial.println("Starting motor");

  // analogWrite(MOTOR_B_1A, 255);
  // analogWrite(MOTOR_B_1B, 0);

  //analogWrite swapped
  // analogWrite(MOTOR_B_1A, 0);
  // analogWrite(MOTOR_B_1B, 255);
  //the direction the motor spins reveresed with the power values swapped

  //analogWrite value changed to 150
  // analogWrite(MOTOR_B_1A, 150);
  // analogWrite(MOTOR_B_1B, 0);
  //the speed of the motor decreased with the power value reduced

  //change to analogWrite value, delay, and direction for the video
  analogWrite(MOTOR_B_1A, 0);
  analogWrite(MOTOR_B_1B, 150);
  //should spin in the opposite direction at a slower speed than before and for longer

  // delay(5000);
  //modified delay value
  delay(10000);
  //the outcome was that it spun for longer which is expected as its the delay before the ESP32 calls analogWrite again

  analogWrite(MOTOR_B_1A, 0);
  analogWrite(MOTOR_B_1B, 0);
  
  Serial.println("Stopped. Press RESET to repeat.");
}
void loop() {}
