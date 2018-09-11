import selectors
import socket
import types


class Server:

    def __init__(self, host, port):
        self._address = (host, port)

        self._selector = selectors.DefaultSelector()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self._socket.bind(self._address)
        self._socket.listen(100)
        self._socket.setblocking(False)

        self._selector.register(self._socket, selectors.EVENT_READ, self._accept)

    def _accept(self, sock, mask):
        conn, addr = sock.accept()  # Should be ready
        print('accepted', conn, 'from', addr)
        conn.setblocking(False)
        self._selector.register(conn, selectors.EVENT_READ, self._read)

    def _read(self, conn, mask):
        data = conn.recv(1000)  # Should be ready
        if data:
            print('echoing', repr(data), 'to', conn)
            conn.send(data)  # Hope it won't block
        else:
            print('closing', conn)
            self._selector.unregister(conn)
            conn.close()






