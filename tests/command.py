import re
# command = {
#     'name': 'Brent',
#     'command': 'zoom:199'
# }
#
# val = ".+:([0-9]+)"
# find = re.findall(val, command['command'])
# search = re.search(val, command['command'])
# match = re.match(val, command['command'])
# print("Searching String \"{string}\":\n\tregex: {regex}\n\tresult: {result}"
#       .format(
#         string=command['command'],
#         regex=val,
#         result=type(find[0])
#         ))
# print("Searching String \"{string}\":\n\tregex: {regex}\n\tresult: {result}"
#       .format(
#         string=command['command'],
#         regex=val,
#         result=search
#         ))
# print("Matching String \"{string}\":\n\tregex: {regex}\n\tresult: {result}"
#       .format(
#         string=command['command'],
#         regex=val,
#         result=match
#         ))
#
# ty = "[a-z]+"
# search = re.search(ty, command['command'])
# match = re.match(ty, command['command'])
# find = re.findall(ty, command['command'])
# print(search)
# print(match)
# print(find)

command = "forward"
regex = "[a-z]+"
command_type = re.match(regex, command)[0]
print(command_type)
# print("Value: {value} of type {type}".format(type=command_type, value=type(command_type)))
if command_type == 'zoom':
    value = "[0-9]+"
    command_value = int(re.search(value, command)[0])
    print(command_value)
    # print("Value: {value} of type {type}".format(type=command_value, value=type(command_value)))
else:
    print('Something else.')
