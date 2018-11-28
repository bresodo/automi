import os
import re

base_dir = os.path.dirname(os.path.realpath(__file__))
dir = '../icons'

files = os.listdir(dir)
patterns = ['capture', 'forward', 'backward', 'left', 'right', 'image']
results = {}

for pattern in patterns:
    for file in files:
        result = re.search(r'^icon_{pattern}[_\w]*\.png$'.format(pattern=pattern), file)
        if not result is None:
            split = re.split('_', result.group())
            print(split[-1])
            print(split)
            if split[-1] == 'on.png':
                results[pattern] = file
            elif split[-1] == 'off.png':
                results[pattern] = file
            elif split[-1] == 'hover.png':
                results[pattern] = file
            else:
                results[pattern] = file
print(results)