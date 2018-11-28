import base64
import re

import cv2
import logging
import queue
import socket
import threading


class VideoServer:
    def __init__(self, ip, port):
        self._clients = {object: {'conn': object, 'addr': None, 'name': 'Hello'}}
        self._max_clients = 20
        self.latest_connection = None
        self._is_listening = False

        self.logger = logging.getLogger(str(VideoServer))
        self.logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler("logs/video_server.log")
        handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(funcName)s:line-%(lineno)d->%(message)s'))
        self.logger.addHandler(handler)

        self._address = (ip, port)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self):
        self.logger.debug("Starting Video Server.")
        counter = 20
        while not self._is_listening and counter > 0:
            if not self._is_listening:
                try:
                    self.logger.debug("Binding address {}:{}".format(self.address[0], self.address[1]))
                    self._socket.bind(self._address)
                    self._socket.listen(self._max_clients)
                    self._is_listening = True
                    self.logger.debug('Server is now listening')
                except socket.error:
                    self.logger.debug("Unable to use current address...{0}".format(self.address))
                    self._is_listening = False
            else:
                self.logger.debug("Unable to start server -> Server is already started/Not yet started.")

            counter -= 1

        if self._is_listening: return True
        else: return False

    def stop(self):
        if self._is_listening:
            self.logger.debug("Closing server socket.")
            self._socket.close()
            self._is_listening = False
            self.logger.debug("Server socket closed.")
        else:
            self.logger.debug("Unable to close server -> Server is already closed.")
            self._is_listening = True

    def reset(self, address):
        print('Resetting')
        self.stop()
        self._address = address
        self.start()
        print('Resetted')

    def accept_connection(self):
        self.logger.debug("Waiting for connection at {}:{}".format(self.address[0], self.address[1]))
        conn, addr = self._socket.accept()
        self.logger.debug("Connection accepted at {}:{}".format(self.address[0], self.address[1]))
        self.logger.debug("Receiving client name.")
        name = conn.recv(32).decode('utf-8')  # Get name of client
        name = re.sub(r'alive$', '', name)
        for client in self._clients:
            if self._clients[client]['name'] == name:
                self.logger.debug("accept_connection: Client already exists.")
                return
        self.logger.debug("Client name:{name} received.".format(name=name))
        self._clients[conn] = {'conn': conn, 'addr': addr, 'name': name}
        self.latest_connection = conn
        return conn, addr

    def send_frame(self, conn, frame):
        frame_size = len(frame)
        size = ""
        if len(str(frame_size)) < 8:
            size_difference = 8 - len(str(frame_size))
            size = ("0" * size_difference) + str(frame_size)
        try:
            conn.sendall(str.encode("{0}".format(size)))
            conn.sendall(frame)
            return True
        except socket.error:
            self.logger.debug("Unable to send frames -> Client: {client} is currently disconnected".format(client=conn))
            return False

    @property
    def latest_connection(self):
        return self._latest_connection

    @latest_connection.setter
    def latest_connection(self, conn):
        self._latest_connection = conn

    @property
    def clients(self):
        return self._clients

    @clients.setter
    def clients(self, conn):
        for client in self._clients:
            temp_conn = self._clients[client]['conn']
            if conn == temp_conn:
                self.logger.debug("Client disconnected -> Removing Client: {0} at {1}"
                                  .format(self._clients[client]['addr'],  self._clients[client]['name']))
                self._clients.pop(client)
                self.logger.debug("Client disconnected -> Client Removed.")
                return

    @property
    def address(self):
        return self._address

    @property
    def is_listening(self):
        return self._is_listening


class CommunicationServer:
    def __init__(self, ip, port):
        self.logger = logging.getLogger(str(CommunicationServer))
        self.logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler("comm_server.log")
        handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(funcName)s:line-%(lineno)d->%(message)s'))
        self.logger.addHandler(handler)

        self._is_listening = False;
        self._address = ip, port
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self):
        self.logger.debug("Starting Communication Server.")
        if not self._is_listening:
            try:
                self.logger.debug("Binding address {}:{}".format(self._address[0], self._address[1]))
                self._socket.bind(self._address)
                self._socket.listen(10)
                self._is_listening = True
            except socket.error:
                self.logger.debug("Unable to use current address...{0}".format(self._address))
        else:
            self.logger.debug("Unable to start server -> Server is already started/Not yet started.")

    def stop(self):
        if self._is_listening:
            self.logger.debug("Closing server socket.")
            self._socket.close()
            self._is_listening = False
            self.logger.debug("Server socket closed.")
        else:
            self.logger.debug("Unable to close server -> Server is already closed.")

    def accept_connection(self):
        self.logger.debug("Waiting for connection at {}:{}".format(self._address[0], self._address[1]))
        conn, addr = self._socket.accept()  # Wait until client connects
        name = conn.recv(1024).decode('utf-8')  # Get name of client
        # self.clients[name] = [conn, addr, name, 'false', self.client_id]  # Add the {conn, name, permission} to the clients dictionary
        self.logger.debug("Connection accepted at {}:{}".format(addr[0], addr[1]))
        return conn, addr

    def receive_command(self, conn):
        command = conn.recv(1024).decode('utf-8')
        if command:
            self.logger.debug('Command received -> '.format(command))
            return True, command
        else:
            self.logger.debug('No command received.')
            return False, None

    @property
    def address(self):
        return self._address



