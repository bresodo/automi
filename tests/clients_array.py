conn = "asdasdasdasdasd"
names = [
    "Brentjeffson",
    'Jeffson',
    'Florendo',
    'Bj'
]
client_id = 0
address = 'localhost', 9999

clients = {
    'client-1': [conn, address, names[0], client_id],
    'client-2': [conn, address, names[1], client_id],
    'client-3': [conn, address, names[2], client_id],
    'client-4': [conn, address, names[3], client_id]
    }
clients_list = []
for name in names:
    clients_list.append({'conn':conn,'address':address,'name':name, 'client-id':client_id})

key = 0
for client in clients_list:
    print('id: {id}\nname:{name}'.format(id=key, name=client['name']))
    key += 1

for client in clients_list:
    print(client)

print(clients_list[-1:])
print(clients_list[-1:][0]['name'])

# client[0] = {'conn':conn, 'name':name, 'permission':'false'}
# print(client[0]['conn'])

# print(clients[-1:])
clients['Brent'] = [conn, address, names[3], client_id]
clients['Brent'] = [conn, address, names[2], client_id]
for key in clients:
    print('Key: {key}\nClient: {client}'.format(key=key, client=clients[key]))