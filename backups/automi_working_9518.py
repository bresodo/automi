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

        self.recording = False

        self.camera = Camera(0)
        self.camera.start()
        self.server = server.VideoServer("", 9765)
        self.server.start()

        self.camera_thread = CameraThread(self.camera)
        self.camera_thread.start()
        self.server_thread = ServerThread(self.server, self.camera)
        self.server_thread.start()

        self._setup_widgets()
        self._setup_signals()

    def closeEvent(self, QCloseEvent):
        self.camera_thread.exit()
        self.camera.stop()

        self.server_thread.exit()
        self.server.stop()
        QCloseEvent.accept()

    def _setup_widgets(self):
        self.frame_label.setScaledContents(True)
        self.frame_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)

    def _setup_signals(self):
        # Connect to thread signals
        self.camera_thread.ready_frame.connect(self._update_frame)
        self.camera_thread.ready_frame.connect(self._save_video)

        # Connect control signals
        self.camera_icon.clicked.connect(lambda: self._capture_image(1))
        self.video_icon.clicked.connect(lambda: self._start_recording())

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
                self.writer.write(self.camera_thread.image_raw())
            except:
                print("Done saving.")

    def _capture_image(self, amount):
        # uniq_id = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch()
        uniq_id = str(uuid.uuid4().hex)
        if self.camera.started:

            frame = self.camera_thread.image_raw()

            cv2.imwrite('image_{0}.png'.format(uniq_id), frame)
            self.statusbar.showMessage("Saving Image: image_{0}.png".format(uniq_id))
        else:
            print('CameraErr: Camera is turned off.')

    def _update_frame(self):
        pixmap = QtGui.QPixmap(self.camera_thread.image_frame())
        self.frame_label.setPixmap(pixmap)


# class ServerThread(QtCore.QThread):
#
#     def __init__(self, server, camera):
#         QtCore.QThread.__init__(self)
#         self._camera = camera
#         self._server = server
#         self._address = ("", 9766)
#         self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#
#     def __del__(self):
#         self.wait()
#         print("Closing Server Thread.")
#
#     def run(self):
#         print("Server Thread: Server Running.")
#         self._server_socket.bind(self._address)
#         self._server_socket.listen(5)
#
#         client_id = 0
#         clients = {}
#         while True:
#             print("Waiting for connections at: {0}".format(self._address))
#             conn, addr = self._server_socket.accept()
#             client_id += 1
#             clients[client_id] = addr
#             client_thread = threading.Thread(name="client-thread: {0}".format(client_id), target=self._client_handler,
#                                              args=(conn, addr, client_id))
#             client_thread.start()
#             # self.client_handler(conn, addr, client_id)
#             print('Connection accepted at: {0}'.format(addr))
#             print("Clients: {0}".format(clients))
#
#     def _client_handler(self, conn, addr, id):
#         with conn:
#             while True:
#                 retval, frame = self._camera.read_frame()
#                 if retval:
#                     print(frame)
#                     # frame = cv2.flip(frame, 1)
#
#                     retval, buffer = cv2.imencode('.jpg', frame)
#                     if retval:
#                         image_bytes = base64.b64encode(buffer)
#                         frame = image_bytes
#                     frame_size = len(frame)
#                     size = ""
#                     if len(str(frame_size)) < 8:
#                         size_difference = 8 - len(str(frame_size))
#                         size = ("0" * size_difference) + str(frame_size)
#                     # print("Payload:\n\tSize: {size}\n\tContent: {content}".format(size=frame_size, content=frame))
#                     conn.sendall(str.encode("{0}".format(size)))
#                     conn.sendall(frame)
#         print("Client:{0} - {1} disconnected.".format(id, addr))

class ServerThread(QtCore.QThread):

    def __init__(self, server, camera):
        QtCore.QThread.__init__(self)
        self._camera = camera
        self._server = server

    def __del__(self):
        self.wait()
        print("Closing Server Thread.")

    def run(self):
        # frame_updater_thread = threading.Thread(name="frame-updater-thread", target=self._frame_updater)
        # frame_updater_thread.start()
        while True:
            print("Waiting for connections at: {0}".format(self._server.address))
            conn, addr = self._server.accept_connection()
            client_thread = threading.Thread(name="client-thread: {0}", target=self._client_handler,
                                             args=(conn,))
            client_thread.start()

    def _client_handler(self, conn):
        with conn:
            try:
                while True:
                    retval, frame = self._camera.read_frame()
                    # frame = cv2.flip(frame, 1)
                    if retval:
                        retval, buffer = cv2.imencode('.jpg', frame)
                        if retval:
                            image_bytes = base64.b64encode(buffer)
                            frame = image_bytes
                            # self._frame_queue.put(frame)  # Add a converted frame to queue, ready for sending
                            self._server.send_frame(conn, frame)
            except socket.error:

                print("Client {} disconnected".format(conn))

class CameraThread(QtCore.QThread):
    ready_frame = QtCore.pyqtSignal()

    def __init__(self, camera):
        QtCore.QThread.__init__(self)
        self._camera = camera
        self._raw_frame = None

    def __del__(self):
        self.wait()

    def run(self):
        while True:
            # Get frame from camera
            retval, self._raw_frame = self._camera.read_frame()
            if not retval:
                print("Camera Thread: No Frame found!")
            else:
                self._raw_frame = cv2.flip(self._raw_frame, 1)
                # Emit signal indicating frame is ready
                self.ready_frame.emit()

    def image_frame(self):
        frame = self._convert_frame(self._raw_frame)
        return frame

    def image_raw(self):
        return self._raw_frame

    def _convert_frame(self, frame):
        try:
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            frame = QtGui.QImage(frame.data, width, height, bytes_per_line,
                                 QtGui.QImage.Format_RGB888).rgbSwapped()  # Working
        except:
            print("Camera Thread: No Frame to convert")
        return frame

    @property
    def camera(self):
        return self._camera


# class Server:
#
#     def __init__(self, host, port):
#         self._host = host;
#         self._port = port;
#         self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#
#     def start(self):
#         print('Binding Address{host}:{port}'.format(host=self._host, port=self._port, ))
#         self._server_socket.bind((self._host, self._port))
#         print('Listening on port:{0}'.format(self._port))
#         self._server_socket.listen()
#         # self._server_socket.setblocking(False)
#
#     def stop(self):
#         self._server_socket.close()
#
#     def send(self, conn, message):
#         conn.sendAll(message)
#
#     def send_frame(self, conn, frame):
#         status = conn.sendAll(frame)
#         while not status is None:
#             status = conn.sendAll(frame)
#
#     def receive(self):
#         pass
#
#     def accept_connection(self):
#         # Blocks thread while waiting for connection
#         conn, addr = self._server_socket.accept()
#         return conn, addr
#
#     def close_connection(self):
#         pass
#
#     def broadcast(self):
#         pass


class Camera:
    def __init__(self, index):
        print("Camera: Initializing Camera")
        self._camera_index = index
        self._started = False
        self._capture = None

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

    # @staticmethod
    # def _convert_frame(frame):
    #     # frame = cv2.flip(frame, 1)
    #     height, width, channel = frame.shape
    #     bytes_per_line = 3 * width
    #
    #     # frame = cv2.flip(frame, 1)
    #     # img_down = cv2.pyrDown(frame)
    #     # img_down = np.float32(img_down)
    #     # cv_rgb_img = cv2.cvtColor(img_down, cv2.CV_8S)
    #     # frame = QtGui.QImage(cv_rgb_img.data, cv_rgb_img.shape[1], cv_rgb_img.shape[0], QtGui.QImage.Format_RGB888)
    #     frame = QtGui.QImage(frame.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888).rgbSwapped() # Working
    #     # frame = QtGui.QImage(frame.data, width, height, QtGui.QImage.Format_RGB888) # Working
    #     return frame

    @property
    def started(self):
        return self._started


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    screen = app.primaryScreen()
    size = screen.size()
    print("Screen Resolution: {0} x {1}".format(size.width(), size.height()))
    window = Window()
    # window.setGeometry(0, 0, size.width()/2, size.height()/2)
    window.show()
    sys.exit(app.exec_())
















