from time import sleep
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)


class Servo:

    def __init__(self, pin):
        self.pin = pin
        GPIO.setup(pin, GPIO.OUT)  # PWM PINS 17

        self.pwm = GPIO.PWM(self.pin, 50)
        self.pwm.start(2.5)

    def __del__(self):
        self.set_angle(0)
        self.pwm.stop()

    def set_angle(self, angle):
        duty = angle / 18 + 2
        GPIO.output(self.pin, True)
        self.pwm.ChangeDutyCycle(duty)
        sleep(0.5)
        GPIO.output(self.pin, False)
        self.pwm.ChangeDutyCycle(0)


class Stepper:
    # _DIR = 20   # Direction GPIO Pin
    # _STEP = 21  # Step GPIO Pin
    _CW = 1  # Clockwise Rotation
    _CCW = 0  # Counterclockwise Rotation

    # _SPR = 200   # Steps per Revolution (360 / 1.8)
    # _DELAY = .0208  # Affects the speed of the rotation

    def __init__(self, dir=20, step=21, step_angle=1.8, delay=0.0208, resolution=32, mode_pins=(14, 15, 18)):
        self._RESOLUTION_VALUE = {
            '1': (0, 0, 0),
            '2': (1, 0, 0),
            '4': (0, 1, 0),
            '8': (1, 1, 0),
            '16': (0, 0, 1),
            '32': (1, 0, 1)
        }

        self._DIR = dir
        self._STEP = step
        self._SPR = 360 / step_angle  # steps per rotation (200)
        self._DELAY = delay
        self._RESOLUTION = resolution
        self._MODE_PINS = mode_pins  # Microstep Resolution GPIO Pins
        self._step_count = self._SPR

        self.setup_pins()

        self._step_count = int(self._SPR * self._RESOLUTION)  # calculate number of steps multiplied to resolution
        self._DELAY = self._DELAY / self._RESOLUTION  # delay is divided by resolution to reduce the delay due to higher number of steps

    def setup_pins(self):
        GPIO.setup(self._DIR, GPIO.OUT)  # Pin for direction
        GPIO.setup(self._STEP, GPIO.OUT)  # Pin for step
        GPIO.output(self._DIR, self._CW)  # Output direction for pin
        GPIO.setup(self._MODE_PINS, GPIO.OUT)  # Pin for mode m0,m1,m2
        GPIO.output(self._MODE_PINS, self._RESOLUTION_VALUE[str(self._RESOLUTION)])  # Output for mode

    def change_setting(self, type, value):
        if type == 'dir':
            self._DIR = value
        elif type == 'step':
            self._STEP = value
        elif type == 'delay':
            self._DELAY = value
        elif type == 'spr':
            self._SPR = 360 / value
            self._step_count = self._SPR * self._RESOLUTION
            self._DELAY = self._DELAY / self._RESOLUTION
        elif type == 'resolution':
            self._RESOLUTION = value
            GPIO.output(self._MODE, self._RESOLUTION_VALUE[str(self._RESOLUTION)])
            self._step_count = self._SPR * self._RESOLUTION
            self._DELAY = self._DELAY / self._RESOLUTION
        elif type == 'mode':
            self._MODE_PINS = value

    def rotate(self, drc):  # move stepper by half the max step count 6400/2 = 3200 half rotation
        self._set_direction(drc)
        for i in range(int(self._step_count/2)):
            self._move()

    def step_rotate(self, drc):  # Move the stepper motor only by one step
        self._set_direction(drc)
        self._move()

    def _move(self):
        GPIO.output(self._STEP, GPIO.HIGH)
        sleep(0.000002)
        GPIO.output(self._STEP, GPIO.LOW)
        sleep(0.000002)

    def _set_direction(self, drc):
        if drc == 'cw':
            GPIO.output(self._DIR, self._CW)
        elif drc == 'ccw':
            GPIO.output(self._DIR, self._CCW)

    def __str__(self):
        return ('Settings:\nDirection:{}\nStep:{}\nDelay:{}\nSPR:{}\nResolution:{}\nMode:{}'.format(
            self._DIR, self._STEP, self._DELAY, self._SPR, self._RESOLUTION, self._MODE_PINS
        ))

# DIR = 20   # Direction GPIO Pin
# STEP = 21  # Step GPIO Pin
# CW = 1     # Clockwise Rotation
# CCW = 0    # Counterclockwise Rotation
# SPR = 200   # Steps per Revolution (360 / 7.5)
#
# GPIO.setmode(GPIO.BCM)
# GPIO.setup(DIR, GPIO.OUT)
# GPIO.setup(STEP, GPIO.OUT)
# GPIO.output(DIR, CW)
#
# step_count = SPR
# delay = .0208
#
# for x in range(step_count):
#     GPIO.output(STEP, GPIO.HIGH)
#     sleep(delay)
#     GPIO.output(STEP, GPIO.LOW)
#     sleep(delay)
#
# sleep(.5)
# GPIO.output(DIR, CCW)
# for x in range(step_count):
#     GPIO.output(STEP, GPIO.HIGH)
#     sleep(delay)
#     GPIO.output(STEP, GPIO.LOW)
#     sleep(delay)
# stepper = Stepper(dir=20, step=21, step_angle=1.8, delay=0.0208, resolution=32, mode_pins=(14, 15, 18))
# total_steps = 0
# for i in range(12):
#     print('Revolution: ' + str(i))
#     for x in range(6400):
#         stepper.rotate('cw')
#         total_steps += 1
#     print('Steps: ' + str(total_steps))


GPIO.cleanup()