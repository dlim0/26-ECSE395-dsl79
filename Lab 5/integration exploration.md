Daniel Lim

Lab 5: ESP32 Integration Exploration
===
>This is the final lab we are messing with ESP32 and the purpose of this lab is to create a "smart system" using a sensor/actuator of our choosing.

- I am using VSCode to upload the files for the esp32 and using it to write and preview the md files as well.
- I am using sensor PIR Motion Module (HC-SR501) and actuator passive buzzer module (PWM) and using them in this lab to create a smart system.
- From the datasheets for the HC-SR501  and the PWM I was able to determine the actuator/sensor specific commands to code in and how they work (sensor has tone and pitch) (HC-SR501 has an active high and low state based on motion and needs 60 seconds to initialize)
- PIR Motion Information: https://docs.sunfounder.com/projects/ultimate-sensor-kit/en/latest/components_basic/13-component_pir_motion.html
- PWM Information: https://docs.sunfounder.com/projects/umsk/en/latest/03_esp32/esp32_lesson32_passive_buzzer.html#esp32-lesson32-passive-buzzer


- For my specific stakeholders issue a PIR Motion Module is a potential sensor and a PWM is a potential actuator that would be relevant towards the problem at hand. Because we want to be able to create a prototype that is able to detect deer (may not end up being PIR Motion Module based) and notify/deter them (notification is the aim of this lab as the PWM is serving that purpose). So the smart system being created is a motion detector that triggers the buzzer.

1. The code is found in Lab 5 folder in the GitHub repo 26-ECSE395-dsl79 (linked via Canvas)
2. The platformio.ini will be able to upload main onto the ESP32 and run the program on main (so long as platformio.ini's default env is set to the main.cpp or as long as there isn't any other cpp on the project folder opened)
3. Upload the code onto the ESP32 and then run the function using a USB-C connection for live ground and voltage
4. With the active power and code running see if the function of buzzer happens with the proper amount of motion detected.

Time Reporting and Reflection
===
1. This lab took about 3 hours to complete (mostly the software implementation (and reading datasheets) because hardware is straight forward if you refer to the images on the .md)
2. I would say the assignment is hard
3. I tried to be ambitious and thought about a multisensor/actuator based integration, but given my personal time constraints and difficulty of considering more parts made it not a feasible implementation. The hardest thing is that we are working with multiple sensors and actuators from the jump (minimum 2 components made up of 1 actuator and 1 sensor), so it is a more sophisticated design compared to our previous labs, and with no skeleton it required more cross referencing to old code. Given the new components I decided to work with I had to look at the datasheets given to see what was adjustable and what is tolerable/safe to do which took more time.
4. I am still comfortable with the course content because as a Computer Engineering major I am amply exposed to both hardware and software solutions
5. N/A