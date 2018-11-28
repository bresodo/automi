from time import sleep

from motor import AdaServo


servo = AdaServo(0, 50)
while True:
    angle = int(input('Angle(0-180): '))
    servo.set_angle(angle)

# while True:
#     # min_tick = int(input('min: '))
#     max_tick = int(input('max: '))
#     servo.set_angle(max_tick)


# for i in range(100, 510, 10):
#     servo.set_angle(i)
#     print(i)
    # sleep(0.1)
# for i in range(492, 82, -1):
#     servo.set_angle(i)
#     print(i)
#     # sleep(0.1)



