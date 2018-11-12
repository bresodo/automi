import threading
from queue import Queue
from motor import Servo

# pin = int(input('Enter Servo Pin: '))
servo1 = Servo(17)
servo2 = Servo(18)
q = Queue()

def worker():
    while True:
        (pin, angle) = q.get()
        print('Pin: {} at {}'.format(pin, angle))
        if angle == 999:
            q.task_done()
            break
        if pin == 17:
            servo_1(angle)
            q.task_done()
        elif pin == 18:
            servo_2(angle)
            q.task_done()


def servo_1(angle):
    servo1.set_angle(angle)

def servo_2(angle):
    servo2.set_angle(angle)

thread_no = []

thread1 = threading.Thread(target=worker)
thread2 = threading.Thread(target=worker)
thread1.start()
thread2.start()
thread_no.append(thread1)
thread_no.append(thread2)

while True:
    angle = int(input('Enter Angle(0-180): '))
    print(angle)
    q.put([17, angle])
    q.put([18, angle])




