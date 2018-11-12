from time import sleep

prev_pos = 60
position = prev_pos
action = 'inc'
step = 10
if action == 'inc' and position < 180:
    position += step
    half_step = 1
elif action == 'dec' and position > 0:
    position -= step
    half_step = -1

for i in range(prev_pos, position, half_step):
    print(i+half_step)
    sleep(0.5)