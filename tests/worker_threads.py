import time
import threading
from queue import Queue


commands = Queue()

num_workers = 2


def command_worker():
    while True:
        command = commands.get()
        if command is None:
            commands.task_done()
            break
        proccess_command(command)
        commands.task_done()


def proccess_command(command):
    print('Processing Command')
    print('Type: {type}\nValue: {value}'.format(type=command[0], value=command[1]))
    time.sleep(2)
    print('Command Processed')


command_worker_thread = []
for t in range(num_workers):
    t = threading.Thread(target=command_worker)
    t.start()
    command_worker_thread.append(t)

commands.put(['type', 'value'])
commands.put(['type', 'value'])

time.sleep(6)
for c in [['type', 'value'], ['type', 'value'], ['type', 'value'], ['type', 'value']]:
    commands.put(c)
    print('Adding New Commands')
    # time.sleep(1)



