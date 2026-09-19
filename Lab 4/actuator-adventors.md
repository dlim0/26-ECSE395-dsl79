Daniel Lim

Lab 4: ESP32 + Actuators
===
>This is the third lab where we are working with an ESP32 and this aim of this assignment is connecting actuators to ESP32. The steps taken to complete this lab will be written below.



- I am using VSCode to upload the files for the esp32 and using it to write and preview the md files as well.
- Following the TT Motor.md I am rewriting the skeletoncode to be able to run the motor.
- Following the instructions on Canvas as well lets me get findings on the specific values I am modifying
- Using the skeleton code instructions for variable declaration I was able to fill in data to work through TT Motor Rotate
- Throughout the lab I utilized the Lab 4 video to help me complete the related code.

**TT Motor Findings:**
- Adjusting the value of the in analogWrite is related to the amount of power being supplied to the motor because the higher the value the faster it spins and the lower the value the slower it spins
- The two motor B calls in analog write (1A and 1B respectively) are calls to the motor that determine the orientation that the motor spins so switching the values flip the direction its moving (when facing the motor 1A spins CCW and 1B spins CW)
- The delay value is the delay (in ms) before the next analogWrite command is called (which 0's everything out) so the fact that increasing the delays value made the motor spin for longer before stopping let me make that conclusion (and decreasing it makes the motor spin for less time)

**TT Motor Rotate Findings:**
- Using the directions and skeleton code and placeholders from the skeleton code I was able to fill in the blanks for the commented code to get the motor to rotate as expected
- From my findings in TT Motor I was easily able to figure out which motor had to be set for CCW and which motor had to be set for CW orientation
- Thanks to the TT Motor findings I was able to know that each value entered in the delay equates to x milliseconds of delay

**Servo Motor Findings** 

- Questions related to Lab 4
1. This assignment took me about 3 hours to complete
2. I would rate this assignment low level difficulty, but it is mostly because the criteria was well defined
3. N/A
4. I feel very comfortable with the course content so far.
5. No feedback needed so far!