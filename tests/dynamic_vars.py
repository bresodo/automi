class Stepper():
    _NUMBER = 0

    def __init__(self):
        self._NUMBER += 1

    def __str__(self):
        return str(self._NUMBER)
