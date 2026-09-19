#include <ESP32Servo.h>
// Don't forget to include the library!!
// From PlatfromIO library, search for ESP32 servo and add it to the project
#include <esp_system.h>

// Define the servo and the pin it is connected to, what is your servo pin?
Servo myServo;
const int servoPin = 25;

// variable for random angle
int randomAngle;

// Variable for pulse width
int pulseWidth;

// Define the minimum and maximum pulse widths for the servo
const int minPulseWidth = 500; // 0.5 ms
const int maxPulseWidth = 2500; // 2.5 ms

void setup() {
  Serial.begin(115200);

  // Attach the servo to the specified pin and set its pulse width range
  myServo.attach(servoPin, minPulseWidth, maxPulseWidth);

  // Set the PWM frequency for the servo
  myServo.setPeriodHertz(50); // Standard 50Hz servo
}

void loop() {
  //  --- SECTION 1: Make a Random Angle Between 0 to 180 ---
  randomAngle = random(0, 181); // random(A,B) includes A but excludes B.

  // ---SECTION 2: Map Pulse Width with Angle
  // from Servo Motor.cpp, what did you learn from using map function?
  pulseWidth = map(randomAngle, 0, 180, minPulseWidth, maxPulseWidth);
  myServo.writeMicroseconds(pulseWidth); // writing pulse width to servo

  Serial.print("Angle: ");
  Serial.print(randomAngle); //prints the randomly generated angle to the serial monitor
  Serial.print(" | Pulse (us): ");
  Serial.println(pulseWidth); //prints the pulse width to the serial monitorand completes the line
  delay(1000); // change delay to your own preference
}
