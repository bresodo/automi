import queue
import socket
import uuid

import cv2
import sys

from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5 import QtCore

import automi_ui


class Window(QtWidgets.QMainWindow, automi_ui.Ui_MainWindow):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)

        self.recording = False

        self.camera = Camera(0)
        self.server = Server("localhost", 8888)

        self.camera.start()
        self.server.start()

        self.camera_thread = CameraThread(self.camera)
        self.server_thread = ServerThread(self.server, self.camera)

        self.camera_thread.start()
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
                self.writer.write(self.camera_thread.image_array())
            except:
                print("Done saving.")

    def _capture_image(self, amount):
        # uniq_id = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch()
        uniq_id = str(uuid.uuid4().hex)
        if self.camera.started:

            frame = self.camera_thread.image_array()

            cv2.imwrite('image_{0}.png'.format(uniq_id), frame)
            self.statusbar.showMessage("Saving Image: image_{0}.png".format(uniq_id))
        else:
            print('CameraErr: Camera is turned off.')

    def _update_frame(self):
        pixmap = QtGui.QPixmap(self.camera_thread.image_frame())
        self.frame_label.setPixmap(pixmap)


class ServerThread(QtCore.QThread):

    def __init__(self, server, camera):
        QtCore.QThread.__init__(self)
        self._camera = camera
        self._server = server

    def __del__(self):
        self.wait()
        print("Closing Server Thread.")

    def run(self):
        print("Server Running.")
        while True:  # Indefinitely accept connection.
            # Can accept connection one at a time but can be connected to multiple times.
            conn, addr = self._server.accept_connection()  # Blocks while waiting for a connection
            with conn:
                print('Connected to: {addr}'.format(addr=addr))
                while True: # Send data indefinitely
                    conn.sendall(str.encode("asdfkskfskdjfskjdflskjdfklsjfjsdklfjskdjfskdjfsjdfklsjkdlfj"))


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
                print("No Frame found!")
            else:
                self._raw_frame = cv2.flip(self._raw_frame, 1)
                # Emit signal indicating frame is ready
                self.ready_frame.emit()

    def image_frame(self):
        frame = self._convert_frame(self._raw_frame)
        return frame

    def image_array(self):
        return self._raw_frame

    def _convert_frame(self, frame):
        try:
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            frame = QtGui.QImage(frame.data, width, height, bytes_per_line,
                                 QtGui.QImage.Format_RGB888).rgbSwapped()  # Working
        except:
            print("No Frame to convert")
        return frame

    @property
    def camera(self):
        return self._camera


class Server:

    def __init__(self, host, port):
        self._host = host;
        self._port = port;
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self):
        print('Binding Address{host}:{port}'.format(host=self._host, port=self._port, ))
        self._server_socket.bind((self._host, self._port))
        print('Listening on port:{0}'.format(self._port))
        self._server_socket.listen()
        # self._server_socket.setblocking(False)

    def stop(self):
        self._server_socket.close()

    def send(self, conn, message):
        conn.sendAll(message)

    def send_frame(self, conn, frame):
        status = conn.sendAll(frame)
        while not status is None:
            status = conn.sendAll(frame)

    def receive(self):
        pass

    def accept_connection(self):
        # Blocks thread while waiting for connection
        conn, addr = self._server_socket.accept()
        return conn, addr

    def close_connection(self):
        pass

    def broadcast(self):
        pass


class Camera:
    def __init__(self, index):
        print("Initializing Camera")
        self._camera_index = index
        self._started = False
        self._capture = None

    def start(self):
        if not self._capture:
            print("Starting Camera.")
            self._capture = cv2.VideoCapture(self._camera_index)
            self._started = True
        else:
            print("Camera is already on.")
            self._started = False

    def stop(self):
        if self._capture.isOpened():
            print('Stopping camera.')
            self._capture.release()
            self._capture = None
            self._started = False
        else:
            print('Camera is already off/ Not yet started.')
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
                frame = -1
            return True, frame
        else:
            return False, "No Frame"

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
















