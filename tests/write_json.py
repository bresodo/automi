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

# json.dumps() - serialized object as string
# json.dump() - serialized object for file

print(json.dumps(person))
serialized_person = json.dumps(person)
print('Serialized Object:')
print(type(serialized_person))
print(serialized_person)

# json.loads() - deserializes files
# json.load() - deserializes str json
deserialized_person = json.loads(serialized_person)
print('Deserialized Object:')
print(type(deserialized_person))
print(deserialized_person)
print(deserialized_person['name'])