import asyncio
import base64
import queue
import socket
import threading
import uuid

import cv2
import sys

from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5 import QtCore

import server
import automi_ui


class Window(QtWidgets.QMainWindow, automi_ui.Ui_MainWindow):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self.ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]
        self.video_port = 9766
        self.comm_port = self.video_port+10

        self.recording = False
        self.controlled_by = ""

        self.camera = Camera(0)
        self.camera.start()
        # self.comm_server = server.CommunicationServer("", self.comm_port)
        # self.comm_server.start()
        self.video_server = server.VideoServer("", self.video_port)
        self.video_server.start()

        self.camera_thread = CameraThread(self.camera)
        self.camera_thread.start()
        self.video_server_thread = VideoServerThread(self.video_server, self.camera_thread)
        self.video_server_thread.start()
        # self.comm_server_thread = CommunicationServerThread(self.comm_server)
        # self.comm_server_thread.start()

        self._setup_widgets()
        self._setup_signals()

    def closeEvent(self, QCloseEvent):
        self.camera_thread.exit()
        self.camera.stop()

        self.video_server_thread.exit()
        self.video_server.stop()

        # self.comm_server_thread.exit()
        # self.comm_server.stop()
        QCloseEvent.accept()

    def _setup_widgets(self):
        self.frame_label.setScaledContents(True)
        self.frame_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)

    def _setup_signals(self):
        # Connect to thread signals. This functions are automatically called when a signal is emitted from the thread
        self.camera_thread.ready_frame.connect(self._update_frame)
        self.video_server_thread.client_accepted.connect(lambda: self._update_client_menu())
        self.video_server_thread.client_disconnected.connect(self._remove_client_menu)
        self.video_server_thread.received_command.connect(lambda: self._process_command)
        # self.comm_server_thread.received_command.connect(lambda: self._process_command)
        # self.comm_server_thread.client_accepted.connect(lambda: self._update_client_menu(self.comm_server.clients[self.comm_server.client_id][1]))
        # self.camera_thread.ready_frame.connect(self._save_video)

        # Connect control signals
        self.camera_icon.clicked.connect(lambda: self._capture_image(1))
        self.video_icon.clicked.connect(lambda: self._start_recording())

    def _update_client_menu(self):
        for client in self.video_server.clients:
            menu = self.connected_devices_menu.addMenu(client['name'])
            action = menu.addAction("Grant Control")
            action.triggered.connect(lambda: self._grant_control(client['name']))

    def _remove_client_menu(self):
        conn = self.video_server_thread.client_to_remove
        self.video_server.clients = conn
        self.connected_devices_menu.clear()

    def _grant_control(self, client_name):
        self.controlled_by = client_name

    def _process_command(self):
        name, command = self.video_server_thread.command_queue
        if self.controlled_by == name:
            print("Executing command:{command} from:{name}".format(name=name, command=command))
        else:
            print("User:{name} is not permitted.".format(name=name))

    def _start_recording(self):
        # uniq_id = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch()
        uniq_id = str(uuid.uuid4().hex)
        self.recording = not self.recording
        if self.recording:

            res = (640, 480)
            frame_rate = 20.0
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.writer = cv2.VideoWriter('video_{ext}.avi'.format(ext=uniq_id), fourcc, frame_rate, res)
            self.statusbar.showMessage("Recording Video: video_{ext}.mp4".format(ext=uniq_id))
            self.video_icon.setStyleSheet("background-color: red")
        else:
            self.statusbar.showMessage("Done Recording Video: video_{ext}.mp4".format(ext=uniq_id))
            self.video_icon.setStyleSheet("background-color: white")

    def _save_video(self):
        if self.recording:
            try:
                self.writer.write(self.camera_thread.image_raw)
            except IOError:
                print("Done saving.")

    def _capture_image(self, amount):
        # uniq_id = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch()
        uniq_id = str(uuid.uuid4().hex)
        if self.camera.started:

            frame = self.camera_thread.image_raw

            cv2.imwrite('image_{0}.png'.format(uniq_id), frame)
            self.statusbar.showMessage("Saving Image: image_{0}.png".format(uniq_id))
        else:
            print('CameraErr: Camera is turned off.')

    def _update_frame(self):
        frame = self.camera_thread.image_raw
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_size = 0.5
        thickness = 1
        color = (255, 255, 255)
        location = (10, 15)
        text = "{ip}:{port_1}".format(ip=self.ip, port_1=self.video_port)
        cv2.putText(frame, text, location, font, font_size, color, thickness, cv2.LINE_AA)

        try:
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            frame = QtGui.QImage(frame.data, width, height, bytes_per_line,
                                 QtGui.QImage.Format_RGB888).rgbSwapped()  # Working
            pixmap = QtGui.QPixmap(frame)
            self.frame_label.setPixmap(pixmap)
        except:
            print("Main: No Frame to convert")

class CommunicationServerThread(QtCore.QThread):
    client_accepted = QtCore.pyqtSignal()
    received_command = QtCore.pyqtSignal()

    def __init__(self, comm_server):
        QtCore.QThread.__init__(self)
        self._comm_server = comm_server
        self.command = ""

    def __del__(self):
        self.wait()
        print("Closing Server Thread.")

    def run(self):
        while True:
            print("Waiting for connections at: {0}".format(self._comm_server.address))
            conn, addr = self._comm_server.accept_connection()
            client_thread = threading.Thread(name="client-comm-thread: {0}", target=self._client_handler,
                                             args=(conn,))
            client_thread.start()
            self.client_accepted.emit()

    def _client_handler(self, conn):
        print('Starting handler')
        with conn:
            try:
                while True:
                    retval, command = self._comm_server.receive_command
                    if retval:
                        self.command = command
                    self.received_command.emit()
            except socket.error:
                print("Client {} disconnected".format(conn))


class VideoServerThread(QtCore.QThread):
    client_accepted = QtCore.pyqtSignal()
    client_disconnected = QtCore.pyqtSignal()
    received_command = QtCore.pyqtSignal()

    def __init__(self, video_server, camera):
        QtCore.QThread.__init__(self)
        self._camera = camera
        self._server = video_server
        self._frame = None

        self._command_queue = queue.Queue(50)
        self.client_to_remove = None

    def __del__(self):
        self.wait()
        print("Closing Server Thread.")

    def run(self):
        self._client_listener()

    def _client_listener(self):
        handler_loop = asyncio.new_event_loop()
        while self._server.is_listening:
            print("Waiting for connections at: {0}".format(self._server.address))
            conn, addr = self._server.accept_connection()
            client_handler_thread = threading.Thread(
                name="client-video-thread: {name}".format(name=self._server.clients[conn]['name']),
                target=self._client_handler,
                args=(conn,)
            )
            client_handler_thread.start()
            # client_receiver_thread = threading.Thread(
            #     name="client-receiver-thread",
            #     target=self._client_receiver,
            #     args=(conn,)
            # ).start()
            # handler_loop.run_until_complete(self._client_handler(conn))
            # handler_loop.run_until_complete(self._client_receiver(conn))
            self.client_accepted.emit()
        handler_loop.close()

    def _client_handler(self, conn):
        with conn:
            try:
                if self._command_queue.full():
                    self._command_queue.get()
                else:
                    try:
                        command = conn.recv(1024)
                        self._command_queue.put(
                            self._server.clients[conn]['name'],
                            command
                        )
                        self.received_command.emit()
                    except socket.error:
                        print("Client: No Response.")

                sent = self._server.send_frame(conn, self._camera.image_byte)
                while sent:
                    sent = self._server.send_frame(conn, self._camera.image_byte)
            except socket.error:
                self.client_to_remove = conn
                self.client_disconnected.emit()
                print("Client {} disconnected. inside".format(conn))
        self.client_to_remove = conn
        self.client_disconnected.emit()
        print("Client {} disconnected. outside".format(conn))

    def _client_receiver(self, conn):
        while conn:
            if self._command_queue.full():
                self._command_queue.get()
            else:
                try:
                    print('Waiting for command from {name}'.format(name=self._server.clients[conn]['name']))
                    command = conn.recv(1024)
                    self._command_queue.put(
                        self._server.clients[conn]['name'],
                        command)
                    print('Command Received.')
                    self.received_command.emit()
                except socket.error:
                    print("No command")

    @property
    def command_queue(self):
        return self._command_queue.get()

class CameraThread(QtCore.QThread):
    ready_frame = QtCore.pyqtSignal()

    def __init__(self, camera):
        QtCore.QThread.__init__(self)
        self._camera = camera
        self._raw_frame = None

    def __del__(self):
        self.wait()

    def run(self):
        while self._camera.started:
            # Get frame from camera
            retval, frame = self._camera.read_frame()
            if retval:
                self._raw_frame = frame
                self.ready_frame.emit()  # Emit signal indicating frame is ready
            else:
                print("Camera Thread: No Frame found!")

    @property
    def image_frame(self):  # Returns a frame ready to be used for label
        frame = self.image_raw
        try:
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            frame = QtGui.QImage(frame.data, width, height, bytes_per_line,
                                 QtGui.QImage.Format_RGB888).rgbSwapped()  # Working
        except:
            print("Camera Thread: No Frame to convert")
        return frame

    @property
    def image_raw(self):  # Returns an an-altered frame
        return self._raw_frame

    @property
    def image_byte(self):
        return self._camera.frame_queue


class Camera:
    def __init__(self, index):
        print("Camera: Initializing Camera")
        self._camera_index = index
        self._started = False
        self._capture = None
        self._frame_queue = queue.Queue(5)

    def start(self):
        if not self._capture:
            print("Camera: Starting Camera.")
            self._capture = cv2.VideoCapture(self._camera_index)
            self._started = True
        else:
            print("Camera: Camera is already on.")
            self._started = False

    def stop(self):
        if self._capture.isOpened():
            print('Camera: Stopping camera.')
            self._capture.release()
            self._capture = None
            self._started = False
        else:
            print('Camera: Camera is already off/ Not yet started.')
            self._started = False

    def read_frame(self):
        """Returns an opencv numpy array frame. If false returns -1"""
        if self._started:
            ok, raw_frame = self._capture.read()

            if ok:
                frame = raw_frame
                self.frame_queue = frame
                # frame = cv2.flip(raw_frame, 1)
                # if img_type == 'image':
                #     frame = self._convert_frame(frame)
                # elif img_type == 'array':
                #     frame = frame
                # else:
                #     frame = -1
                # gray_image = cv2.cvtColor(fliped_frame, cv2.COLOR_BGR2GRAY)
            else:
                frame = None
            return True, frame
        else:
            return False, None

    @property
    def started(self):
        return self._started

    @property
    def frame_queue(self):
        return self._frame_queue.get()

    @frame_queue.setter
    def frame_queue(self, frame):
        retval, buffer = cv2.imencode('.jpg', frame)
        if retval:
            image_bytes = base64.b64encode(buffer)
            frame = image_bytes
            if self._frame_queue.full():
                self._frame_queue.get()
            else:
                self._frame_queue.put(frame)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    screen = app.primaryScreen()
    size = screen.size()
    print("Screen Resolution: {0} x {1}".format(size.width(), size.height()))
    window = Window()
    # window.setGeometry(0, 0, size.width()/2, size.height()/2)
    window.show()
    sys.exit(app.exec_())
















