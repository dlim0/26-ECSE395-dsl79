//dsl79 changed the int voltage to float to preserve the decimals that the voltage function is going to calculate
/* #include <Arduino.h>

// function prototype
// dsl79: the voltage is declared before conversion function is called.
float voltage(float analogvalue);

// Put your potentiometer pin assignment here
// dsl79: Use GPIO 34 as a connection
const int sensorPin = 34;

void setup() {
    // dsl79: Start serial communication at 115200 baud.
    Serial.begin(115200);
}

void loop() {
    // This is the line for printing in the serial
    // dsl79: reading the GPIO 34 we call the voltage function to convert the reading to estimated volts and then print out the value in the serial monitor
    Serial.println(voltage(analogRead(sensorPin)));
    delay(50); 
}

// function to calculate output voltage
// dsl79: using the formula given to us to calculate the voltage read (rewritten to utilize a float)
float voltage(float analogvalue){
    return analogvalue * 3.3f / 4095.0f;
}
*/
