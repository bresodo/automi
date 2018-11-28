from time import sleep
import RPi.GPIO as GPIO
import Adafruit_PCA9685

GPIO.setmode(GPIO.BCM)

# Pulse Width = 1/Freq = 1/50 = 20 ms = 0.02 seconds
# Time per tick = 4.88x10^-6


class AdaServo:
    def __init__(self, channel, frequency):
        self.channel = channel
        self.frequency = frequency
        self.pwm = Adafruit_PCA9685.PCA9685()
        self.pwm.set_pwm_freq(self.frequency)

    # def set_angle(self, min_tick, max_tick):
    #     # Time per cycle = 20ms
    #     # 2.4ms = 12%
    #     # 81.92ticks = 0.4ms = 0 angle = 0%
    #     # 286.73ticks = 1.4ms = 90 angle = 50%
    #     # 491.52ticks = 2.4ms = 180 angle = 100%
    #     # 1% = 4.92 ticks = 0.024ms = 1.8 angle
    #     # 410 tick = 180 angle = 100%
    #     #
    #     self.pwm.set_pwm(self.channel, min_tick, max_tick)
    #     sleep(1)
    def set_angle(self, angle):
        ticks = int(((angle / 18) * 41) + 82)
        self.pwm.set_pwm(self.channel, 0, ticks)
        sleep(0.5)
        self.pwm.set_pwm(self.channel, 0, 0)

    def set_pin(self, pin):
        self.channel = pin

    def set_freq(self, freq):
        self.pwm.set_pwm_freq(freq)

    def __str__(self):
        return 'Channel: {ch}\nFrequency: {freq}'.format(ch=self.channel, freq=self.frequency)


class Servo:
    def __init__(self, pin):
        self.pin = pin
        GPIO.setup(pin, GPIO.OUT)  # PWM PINS 17

        self._setup()

    def __del__(self):
        self.set_angle(0)
        self.pwm.stop()

    def _setup(self):
        self.pwm = GPIO.PWM(self.pin, 50)  # Frequency is 50Hz
        self.pwm.start(2.5)

    def set_pin(self, pin):
        self.pin = pin
        self._setup()

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

    def __init__(self, dir=None, step=None, step_angle=1.8, delay=0.0208, resolution=None, mode_pins=None):
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

    def change_settings(self, dir=None, step=None, step_angle=1.8, delay=0.0208, resolution=32, mode_pins=(None, None, None)):
        settings = [self._DIR, self._STEP, self._STEP, self._DELAY, self._RESOLUTION, self._MODE_PINS]
        values = [dir, step, step_angle, delay, resolution, mode_pins]
        index = 0
        while index < len(settings):
            if not values[index] is None:
                settings[0] = values[0]
                print('Settings{}: Changing setting'.format(index))
            else:
                print('Setting{}: Changed'.format(index))
            index += 1

    # def change_setting(self, type, value):
    #     if type == 'dir':
    #         self._DIR = value
    #     elif type == 'step':
    #         self._STEP = value
    #     elif type == 'delay':
    #         self._DELAY = value
    #     elif type == 'spr':
    #         self._SPR = 360 / value
    #         self._step_count = self._SPR * self._RESOLUTION
    #         self._DELAY = self._DELAY / self._RESOLUTION
    #     elif type == 'resolution':
    #         self._RESOLUTION = value
    #         GPIO.output(self._MODE, self._RESOLUTION_VALUE[str(self._RESOLUTION)])
    #         self._step_count = self._SPR * self._RESOLUTION
    #         self._DELAY = self._DELAY / self._RESOLUTION
    #     elif type == 'mode':
    #         self._MODE_PINS = value

    def rotate(self, drc):  # move stepper by half the max step count 6400/2 = 3200 half rotation
        self._set_direction(drc)
        for i in range(int(self._step_count)/4):
            self._move()

    def steps_rotate(self, drc, steps):
        self._set_direction(drc)
        for i in range(steps):
            self._move()

    def step_rotate(self, drc):  # Move the stepper motor only by one step
        self._set_direction(drc)
        self._move()

    def _move(self):
        GPIO.output(self._STEP, GPIO.HIGH)
        sleep(self._DELAY)
        GPIO.output(self._STEP, GPIO.LOW)
        sleep(self._DELAY)

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