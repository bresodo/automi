import socket

address = 'localhost', 9766
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(address)
client.sendall('Brentjeffson'.encode())
data = client.recv(4086)
print(data)


while data:
    client.recv(4086)
    print(data)

client.close()