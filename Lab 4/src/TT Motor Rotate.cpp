#include <Arduino.h>

// TODO: Define your pins
// Hint: Look at your wiring. Which pins did you use?
const int MOTOR_B_1A = 25;
const int MOTOR_B_1B = 26;

void setup() {
  // CHANGED: Completed serial and output initialization.
  Serial.begin(115200);

  //TODO: Set your motor pins as OUTPUTs
  pinMode(MOTOR_B_1A, OUTPUT);
  pinMode(MOTOR_B_1B, OUTPUT);

  Serial.println("Starting motor");
}
void loop() {
  //SECTION 1: Clokwise (5s) ---
  Serial.println("Clockwise: 5 seconds");

  //TODO: Write HIGH to one pin and LOW to the other
  digitalWrite(MOTOR_B_1A, HIGH); //CCW
  digitalWrite(MOTOR_B_1B, LOW);  //CW

  delay(5000);

  //--- SECTION 2: Stop (2s) ---
  Serial.println("Stopped: 2 seconds");

  //TODO: Turn off the motor
  digitalWrite(MOTOR_B_1A, LOW);
  digitalWrite(MOTOR_B_1B, LOW);

  delay(2000);

  // --- SECTION 3: Counterclockwise (5s) ---
  Serial.println("Counterclockwise: 5 seconds");

  //TODO: Write HIGH to one pin and LOW to the other
  digitalWrite(MOTOR_B_1A, LOW);
  digitalWrite(MOTOR_B_1B, HIGH);

  delay(5000);

  // --- SECTION 4: Stop (2s) ---
  Serial.println("Stopped: 2 seconds");

  //TODO: Turn off the motor
  digitalWrite(MOTOR_B_1A, LOW);
  digitalWrite(MOTOR_B_1B, LOW);
  delay(2000);
}
