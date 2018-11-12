class Stepper:
    def __init__(self, mode):
        print('Mode-1: {0}\nMode-2: {1}\nMode-3: {2}'.format(mode[0], mode[1], mode[2]))


stepper = Stepper((1,2,3))

resoulution = {
    'full': [(0, 0, 0, 0), 1],
    '1/4': [(1, 0, 0), 4],
    '1/8': [(0, 1, 0), 8],
    '1/16': [(1, 0, 1), 16]
}
print(resoulution['1/4'][0])
print(resoulution['1/4'][1])
