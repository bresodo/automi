import json

person = {
    'name': 'Brentjeffson',
    'age': 222,
}

with open('steppers.txt', 'w') as file:
    json.dump(person, file, ensure_ascii=False)


with open('steppers.txt', 'r') as file:
    data = file.read()
    print(data)



