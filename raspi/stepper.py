from motor import Stepper

settings = [
        {   "dir"           : 5,
            "step"          : 6,
            "step_angle"    : 1.8,
            "delay"         : 0.0208,
            "resolution"    : 32,
            "mode_pins"     : (13, 19, 26)
        },
        {   "dir"           : 20,
            "step"          : 21,
            "step_angle"    : 1.8,
            "delay"         : 0.0208,
            "resolution"    : 32,
            "mode_pins"     : (14, 15, 23)
        }
    ]
step_no = int(input('Stepper(0-1): '))
stepper = Stepper(dir=settings[step_no]['dir'],
                step=settings[step_no]['step'],
                step_angle=settings[step_no]['step_angle'],
                delay=settings[step_no]['delay'],
                resolution=settings[step_no]['resolution'],
                mode_pins=settings[step_no]['mode_pins']) # M0 M1 M2

while True:
    err_rotation = True
    steps = None
    direction = None
    while err_rotation:
        try:
            steps = int(input('Enter Number Of Rotation(1=0.5 Rotation): '))
            err_rotation = False
        except TypeError:
            print('Error: Invalid Input.')
            err_rotation = True

    err_dir = True
    while err_dir:
        direction = input('Enter Direction(cw, ccw): ')
        if direction == 'exit':
            print('Exiting...')
            break
        elif direction == 'ccw' or direction == 'cw':
            for r in range(steps):
                stepper.rotate(direction)
            err_dir = False
        else:
            err_dir = True

