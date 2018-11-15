
# 100% == 360 degrees == 1 revolution == 6400 steps
# 1% == 3.6 degrees
def stepper(percent):
    steps = 6400.0
    step = 0.0
    print('Limit: ' + str((steps*percent)))
    while step <= (steps*percent):
        step += 0.1

    print('Step: {step} - Percent: {percent}'.format(
        step=step,
        percent=percent*100
    ))


stepper(1)  # 1 Revolution
stepper(1.5)  # 1.5 Revolution
stepper(0.5)  # 180 Degrees/ 0.5 Revolution
stepper(0.6)
stepper(0.7)
stepper(0.8)
stepper(0.95)





