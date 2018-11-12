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
        sleep(1)
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
        self._SPR = 360 / step_angle
        self._DELAY = delay
        self._RESOLUTION = resolution
        self._step_count = self._SPR

        GPIO.setup(self._DIR, GPIO.OUT)
        GPIO.setup(self._STEP, GPIO.OUT)
        GPIO.output(self._DIR, self._CW)

        self._MODE_PINS = mode_pins  # Microstep Resolution GPIO Pins
        GPIO.setup(self._MODE_PINS, GPIO.OUT)
        GPIO.output(self._MODE_PINS, self._RESOLUTION_VALUE[str(self._RESOLUTION)])
        print('Resolution: '+str(self._RESOLUTION))
        self._step_count = int(self._SPR * self._RESOLUTION)
        self._DELAY = .00208 / self._RESOLUTION
        print('SPR: ' + str(self._SPR))
        print('Step Count: '+str(self._step_count))

    def change_settings(self, type, value):
        if type == 'dir':
            self._DIR = value
        elif type == 'step':
            self._STEP = value
        elif type == 'delay':
            self._DELAY = value
        elif type == 'spr':
            self._SPR = 360 / value
            GPIO.output(self._MODE, self._RESOLUTION_VALUE[str(self._RESOLUTION)])
            self._step_count = self._SPR * self._RESOLUTION
            self._DELAY = .0208 / self._RESOLUTION
        elif type == 'resolution':
            self._RESOLUTION = value
            GPIO.output(self._MODE, self._RESOLUTION_VALUE[str(self._RESOLUTION)])
            self._step_count = self._SPR * self._RESOLUTION
            self._DELAY = .00208 / self._RESOLUTION

    def rotate(self, drc):
        if drc == 'cw':
            GPIO.output(self._DIR, self._CW)
            # print('Going Down')
        elif drc == 'ccw':
            # print('Going Up')
            GPIO.output(self._DIR, self._CCW)

        for i in range(int(self._step_count/2)):
            # print('Steps: ' + str(i))
            GPIO.output(self._STEP, GPIO.HIGH)
            sleep(self._DELAY)
            GPIO.output(self._STEP, GPIO.LOW)
            sleep(self._DELAY)



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