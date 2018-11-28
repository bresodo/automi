from motor import Stepper

settings = [
        {   "dir"           : 12, #
            "step"          : 6,
            "step_angle"    : 1.8,
            "delay"         : 0.0208,
            "resolution"    : 32,
            "mode_pins"     : (25, 7, 5)
        },
        {   "dir"           : 21, #
            "step"          : 20,
            "step_angle"    : 1.8,
            "delay"         : 0.0208,
            "resolution"    : 32,
            "mode_pins"     : (13, 16, 19)
        }
    ]
step_no = int(
    input(
        'Options:'
        '\n\tLens - 0'
        '\n\tUpdown - 1'
        '\nSelect: '
    ))
stepper = Stepper(dir=settings[step_no]['dir'],
                step=settings[step_no]['step'],
                step_angle=settings[step_no]['step_angle'],
                delay=settings[step_no]['delay'],
                resolution=settings[step_no]['resolution'],
                mode_pins=settings[step_no]['mode_pins']) # M0 M1 M2

running = True
while running:
    err_rotation = True
    steps = None
    direction = None
    while err_rotation:
        try:
            steps = int(input('Enter Number Of Rotation(1 Rotation == 6400 Steps): '))
            err_rotation = False
        except TypeError:
            print('Error: Invalid Input.')
            err_rotation = True

    err_dir = True
    while err_dir:
        direction = input(
            'Enter Direction('
            '\n\tDown - cw '
            '\n\tUp - ccw): ')
        if direction == 'stepper':
            print('Going back to stepper selection.')
            break
        elif direction == 'exit':
            print('Exiting...')
            running = False
            break
        elif direction == 'ccw' or direction == 'cw':
            for r in range(steps):
                stepper.step_rotate(direction)
            err_dir = True
        else:
            print('Selected an invalid option: {opt}'.format(opt=direction))
            err_dir = True

