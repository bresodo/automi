import importlib
# import RPi.GPIO as GPIO
# import Adafruit_PCA9685

# dependencies = ['os', 'GPIO', 'motor', 'Adafruit_PCA9685']
# missing_dependencies = []
# for dependency in dependencies:
#     loader = importlib.find_loader(dependency)
#
#     if loader is not None:
#         print(f'Dependency {dependency} exists!')
#     else:
#         missing_dependencies.append(dependency)
#         print(f'Dependency {dependency} does not exists')
#
#
# print('Missing dependencies.')
# print(missing_dependencies)

dependencies = {
    'os': False,
    'GPIO': False,
    'motor': False,
    'Adafruit_PCA9685': False
}

for dependency, value in dependencies.items():
    loader = importlib.find_loader(dependency)
    if loader is not None:
        dependencies[dependency] = True
    else:
        dependencies[dependency] = False

print(dependencies)
