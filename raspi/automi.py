import asyncio
import base64
import queue
import socket
import threading
import uuid
import json

import cv2
import sys

from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5 import QtCore
from PyQt5.QtCore import QThread
from PyQt5.QtGui import QIcon, QPixmap

from motor import Servo, Stepper

import server
import automi_ui


class Window(QtWidgets.QMainWindow, automi_ui.Ui_MainWindow):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self._settings = None
        self._app_status = True

        try:
            self.ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if
                         not ip.startswith("127.")] or [
                         [(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in
                         [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]
        except:
            print('Please connect to a network.')
        self.video_port = 9766
        self.comm_port = self.video_port+10

        self.recording = False
        self.controlled_by = ""
        self.video_name = ""
        self.image_name = "image_"

        self._commands_queue = queue.Queue()

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
        self.command_processing_thread = threading.Thread(target=self._command_worker)
        self.command_processing_thread.start()
        # self.comm_server_thread = CommunicationServerThread(self.comm_server)
        # self.comm_server_thread.start()

        self.updown_motor = Stepper(dir=20,
                                    step=21,
                                    step_angle=1.8,
                                    delay=0.0208,
                                    resolution=32,
                                    mode_pins=(14, 15, 23))
        self.nosepiece_motor = Stepper(dir=5,
                                    step=6,
                                    step_angle=1.8,
                                    delay=0.0208,
                                    resolution=32,
                                    mode_pins=(13, 19, 26)) # M0 M1 M2
        self.leftright_servo = Servo(17)
        self.forwardbackward_servo = Servo(18)

        self._init_settings()
        self._init_style()

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

    def closeEvent(self, event):
        self._save_settings()
        self._app_status = False
        print('Exiting...')

    def _setup_widgets(self):
        self.frame_label.setScaledContents(True)
        self.frame_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)

        self.zoom_slider.setMaximum(self._settings['zoom_slider']['max_position'])
        self.zoom_slider.setMinimum(self._settings['zoom_slider']['min_position'])
        self.zoom_slider.setSliderPosition(self._settings['zoom_slider']['position'])
        self._set_zoom()

        self.updown_slider.setMaximum(self._settings['updown_slider']['max_position'])
        self.updown_slider.setMinimum(self._settings['updown_slider']['min_position'])
        self.updown_slider.setSliderPosition(self._settings['updown_slider']['position'])

        self.brightness_slider_2.setMaximum(self._settings['brightness_slider']['max_position'])
        self.brightness_slider_2.setMinimum(self._settings['brightness_slider']['min_position'])
        self.brightness_slider_2.setSliderPosition(self._settings['brightness_slider']['position'])

        self.leftright_servo.set_angle(self._settings['left-right_button']['position'])
        self.forwardbackward_servo.set_angle(self._settings['forward-backward_button']['position'])

    def _setup_signals(self):
        # Connect to thread signals. This functions are automatically called when a signal is emitted from the thread
        self.camera_thread.ready_frame.connect(self._update_frame)
        self.video_server_thread.client_accepted.connect(self._update_client_menu)
        self.video_server_thread.client_disconnected.connect(self._remove_client_menu)
        self.video_server_thread.received_command.connect(lambda: self._process_command())
        # self.comm_server_thread.received_command.connect(lambda: self._process_command)
        # self.comm_server_thread.client_accepted.connect(lambda: self._update_client_menu(self.comm_server.clients[self.comm_server.client_id][1]))
        # self.camera_thread.ready_frame.connect(self._save_video)

        # Connect control signals
        self.camera_icon.clicked.connect(lambda: self._capture_image(1))
        self.video_icon.clicked.connect(lambda: self._start_recording())

        # Forward-Backward Button
        self.forward_button.clicked.connect(lambda: self._add_command('button', 'fb', 'inc'))
        self.backward_button.clicked.connect(lambda: self._add_command('button', 'fb', 'dec'))
        # Left-Right Button
        self.left_button.clicked.connect(lambda: self._add_command('button', 'lr', 'inc'))
        self.right_button.clicked.connect(lambda: self._add_command('button', 'lr', 'dec'))
        # Lens Button
        self.change_lens_button.clicked.connect(lambda: self._commands_queue.put(['button', 'cl', None]))
        # Zoom Button
        self.zoom_slider.valueChanged.connect(self._set_zoom)
        # Up/Down Slider
        self.updown_slider.valueChanged.connect(lambda: self._commands_queue.put(['slider', 'updown', None]))

    def _init_style(self):
        pass

    def _init_settings(self):
        with open("settings.json", "r") as read:
            self._settings = json.load(read)
        self.video_port = self._settings['video_port']
        steppers_settings = {
            'function': [
                self.updown_motor, self.nosepiece_motor,
            ],
            'steppers': [
                'updown_slider', 'lens',
            ],
            'settings': [
                "dir", "step", "step_angle", "delay", "resolution", "mode_pins",
            ],
        }
        for x in range(len(steppers_settings['steppers'])):
            print('Setting up setting for ' + steppers_settings['steppers'][x])
            stepper = steppers_settings['function'][x]
            for y in range(len(steppers_settings['settings'])):
                print(steppers_settings['settings'][y])
                stepper.change_setting(
                    'dir',
                    self._settings[steppers_settings['steppers'][x]]['pins'][steppers_settings['settings'][y]])
            stepper.setup_pins()


    def _save_settings(self):
        with open("settings.json", 'w') as file:
            json.dump(self._settings, file)

    def _update_client_menu(self):
        self.connected_devices_menu.clear()
        # self.statusbar.showMessage("Client: {client} Connected.".format(
        #     client=self.video_server.clients[self.video_server_thread.newly_added_client]['name']))
        for client in self.video_server.clients:
            name = self.video_server.clients[client]['name']
            menu = self.connected_devices_menu.addMenu(name)
            action = menu.addAction("Grant Control")
            action.triggered.connect(lambda: self._grant_control(name))
        # menu = self.connected_devices_menu.addMenu(self.video_server.clients[len(self.video_server.clients)-1]['name'])
        # action = menu.addAction("Grant Control")
        # action.triggered.connect(lambda: self._grant_control(self.video_server.clients[len(self.video_server.clients)-1]['name']))

    def _remove_client_menu(self):
        conn = self.video_server_thread.client_to_remove
        if self.controlled_by == self.video_server.clients[conn]['name']:
            self.controlled_by = ""
        self.video_server.clients = conn
        self._update_client_menu()

    def _grant_control(self, client_name):
        print('Granting controll to' + client_name)
        self.controlled_by = client_name

    def _add_command(self, type, command, value):
        print('Adding Command')
        self._commands_queue.put([type, command, value])

    def _command_worker(self):
        while True:
            cmd = self._commands_queue.get()
            print('Command Worker: ' + str(cmd))
            if not self._app_status:
                self._commands_queue.task_done()
                break
            self._execute_command(cmd)
            self._commands_queue.task_done()

    def _execute_command(self, data):
        (type, command, value) = data
        if type == 'button':
            if command == 'lr':
                self._move_stage(command, value)
            elif command == 'fb':
                self._move_stage(command, value)
            elif command == 'cl':
                self._change_lens()
        elif type == 'slider':
            print('Working')
            if command == 'updown':
                print('Going Up/Down')
                self._set_updown()
        print('Executing Command...')

    def _process_command(self):
        # print('Processing command...')
        name = self.video_server_thread.command['name']
        command = self.video_server_thread.command['command']
        if self.controlled_by == name:
            # print("Executing command:{command} from:{name}".format(name=name, command=command))
            # regex = "[a-z]+"
            # command_type = re.match(regex, command)[0]
            command = command.split(":")
            command_type = command[0]
            if command_type == 'zoom':
                # value = "[0-9]+"
                # command_value = int(re.search(value, command)[0])
                command_value = int(command[1])
                self.camera.zoom = command_value
                self.zoom_slider.setValue(command_value)
            elif command_type == 'brightness':
                command_value = int(command[1])
                self.brightness_slider_2.setValue(command_value)
            elif command_type == 'forward':
                self._move_stage('fb', 'inc')
                # self._move_forback('forward')
            elif command_type == 'backward':
                self._move_stage('fb', 'decc')
                # self._move_forback('backward')
            elif command_type == 'left':
                self._add_command('button', 'lr', 'inc')
                # self._move_stage('lr', 'inc')
                # self._move_leftright('left')
            elif command_type == 'right':
                self._add_command('button', 'lr', 'dec')
                self._move_stage('lr', 'dec')
                # self._move_leftright('right')
            elif command_type == 'up':
                if self._settings['updown_slider']['position'] < self._settings['updown_slider']['max_position']:
                    self._settings['updown_slider']['position'] += 1
                    self.updown_slider.setValue(self._settings['updown_slider']['position'])
                    self.updown_motor.rotate('ccw')
            elif command_type == 'down':
                if self._settings['updown_slider']['position'] > self._settings['updown_slider']['min_position']:
                    self._settings['updown_slider']['position'] -= 1
                    self.updown_slider.setValue(self._settings['updown_slider']['position'])
                    self.updown_motor.rotate('cw')
        # else:
        #     print("User:{name} is not permitted.".format(name=name))

    def _move_stage(self, direction, action):
        setting_name = {
            "lr": ['left-right_button', self.leftright_servo],
            "fb": ['forward-backward_button', self.forwardbackward_servo],
        }
        servo = setting_name[direction][1]
        pre_position = self._settings[setting_name[direction][0]]['position']
        post_position = pre_position
        step = self._settings[setting_name[direction][0]]['steps']
        # half_step = None
        if action == 'inc' and post_position < 180:
            post_position += step
            # half_step = 1
        elif action == 'dec' and post_position > 0:
            post_position -= step
            # half_step = -1
        # for i in range(pre_position, post_position, half_step):
        servo.set_angle(post_position)
        self._settings[setting_name[direction][0]]['position'] = post_position
    # def _move_leftright(self, direc):
    #     position = self._settings['left-right_button']['position']
    #     if direc == 'left':
    #         position -= 10
    #         self.leftright_servo.set_angle(position)
    #         print('Move: Left({pos})'.format(pos=position))
    #     elif direc == 'right':
    #         position += 10
    #         self.leftright_servo.set_angle(position)
    #         print('Move: Right({pos})'.format(pos=position))
    #     else:
    #         print('Error: Invalid Direction.')
    #     self._settings['left-right_button']['position'] = position
    #
    # def _move_forback(self, direc):
    #     position = self._settings['forward-backward_button']['position']
    #     if direc == 'forward':
    #         position -= 10
    #         # self.leftright_servo.set_angle(position)
    #         print('Move: Forward({pos})'.format(pos=position))
    #     elif direc == 'backward':
    #         position += 10
    #         # self.leftright_servo.set_angle(position)
    #         print('Move: Backward({pos})'.format(pos=position))
    #     else:
    #         print('Error: Invalid Direction.')
    #     self._settings['forward-backward_button']['position'] = position

    def _change_lens(self):
        lens_index = self._settings['lens']['index']
        current_position = self._settings['lens']['position']['dynamic']
        if lens_index == 0:
            # Rotate Stepper To next lens
            print('Changing Lens: 0->1')
            lens_index = 1
            while current_position < self._settings['lens']['position']['static'][0]:
                current_position += 1
                self.nosepiece_motor.step_rotate('cw')
                self._settings['lens']['position']['dynamic'] = current_position

        elif lens_index == 1:
            # Rotate Stepper clockwise going to lens 2
            print('Changing Lens: 1->2')
            lens_index = 2
            while current_position < self._settings['lens']['position']['static'][1]:
                current_position += 1
                self.nosepiece_motor.step_rotate('cw')
                self._settings['lens']['position']['dynamic'] = current_position

        elif lens_index == 2:
            # Rotate Stepper counter clockwise returning to lens 0
            print('Changing Lens: 2->0')
            lens_index = 0
            while current_position < self._settings['lens']['position']['static'][2]:
                current_position -= 1
                self.nosepiece_motor.step_rotate('ccw')
                self._settings['lens']['position']['dynamic'] = current_position

        self._settings['lens']['index'] = lens_index

    def _set_zoom(self):
        self.camera.zoom = self.zoom_slider.value()
        self._settings['zoom_slider']['position'] = self.zoom_slider.value()

    def _set_updown(self):
        steps = None
        direction = None

        new_position = self.updown_slider.value()
        print('Set Position: ' + str(new_position))
        current_position = self._settings['updown_slider']['position']

        if new_position >= current_position:
            direction = "up"
            steps = new_position - current_position
        elif new_position <= current_position:
            direction = "down"
            steps = current_position - new_position

        for step in range(steps):
            if self._app_status and direction == "up" and current_position < self._settings['updown_slider']['max_position']:
                current_position += 1
                self.updown_motor.rotate('ccw')
                self._settings['updown_slider']['position'] = current_position
                print('Current Position(Up): ' + str(current_position))
            elif self._app_status and direction == "down" and current_position > self._settings['updown_slider']['min_position']:
                current_position -= 1
                self.updown_motor.rotate('cw')
                self._settings['updown_slider']['position'] = current_position
                print('Current Position(Down): ' + str(current_position))
            else:
                print("Limit Reach!")
                break
            self._settings['updown_slider']['position'] = current_position

        print('New Position' + str(self._settings['updown_slider']['position']))

    def _start_recording(self):
        # uniq_id = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch()
        icon = QIcon()
        self.video_icon.setIcon(icon)
        if not self.recording:
            self.video_name = str(uuid.uuid4().hex)
        self.recording = not self.recording
        if self.recording:
            res = (640, 480)
            frame_rate = 20.0
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.writer = cv2.VideoWriter('videos/video_{ext}.avi'.format(ext=self.video_name), fourcc, frame_rate, res)
            self.statusbar.showMessage("Recording Video: video_{ext}.avi".format(ext=self.video_name))
            icon.addPixmap(QPixmap('{baseDir}/VIDON.png'.format(baseDir=self._settings['directories']['icons'])))
            self.video_icon.setIcon(icon)
            # self.video_icon.setStyleSheet("background-color: red")
        else:
            self.statusbar.showMessage("Done Recording Video: video_{ext}.avi".format(ext=self.video_name))
            icon.addPixmap(QPixmap('{baseDir}VIDOFF.png'.format(baseDir=self._settings['directories']['icons'])))
            self.video_icon.setIcon(icon)
            # self.video_icon.setStyleSheet("background-color: white")
    #
    # def _save_video(self):
    #     if self.recording:
    #         try:
    #             self.writer.write(self.camera_thread.image_raw)
    #         except IOError:
    #             print("Done saving.")

    def _capture_image(self, amount):
        # uniq_id = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch()
        uniq_id = str(uuid.uuid4().hex)
        icon = QIcon()
        icon.addPixmap(QPixmap("{baseDir}camONN.png".format(baseDir=self._settings['directories']['icons'])), QIcon.Active)
        self.camera_icon.setIcon(icon)
        if self.camera.started:
            frame = self.camera_thread.image_raw

            cv2.imwrite('{baseDir}{name}_{id}.png'.format(baseDir=self._settings['directories']['images'], name=self.image_name, id=uniq_id), frame)
            self.statusbar.showMessage("Saving Image: {0}_{1}.png".format(self.image_name, uniq_id))
        else:
            icon.addPixmap(QPixmap("{baseDir}camOFFF.png").format(baseDir=self._settings['directories']['icons']))
            self.camera_icon.setIcon(icon)
            print('CameraEvrr: Camera is turned off.')

    def _update_frame(self):
        frame = self.camera_thread.image_raw
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_size = 0.5
        thickness = 1
        color = (255, 255, 255)
        location = (4, 15+5)
        if self.camera.zoom == 0:
            text = "Connection: {ip}:{port_1}".format(ip=self.ip, port_1=self.video_port)
            cv2.putText(frame, text, location, font, font_size, color, thickness, cv2.LINE_AA)
            location = (4, 36 + 5)
            text = "Controller: {control}".format(control=self.controlled_by)
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

        self._command = {'name': '', 'command': ''}
        self.client_to_remove = None
        self.newly_added_client = None

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
            name = self._server.clients[conn]['name']
            self.newly_added_client = conn
            client_handler_thread = threading.Thread(
                name="client-video-thread: {name}".format(name=name),
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
            sent = True
            try:
                while sent:
                    # if self._command.full():
                    #     # print('Command Queue is full')
                    #     self._command.get()
                    # else:
                    try:
                        # print('Receiving command...')
                        command = conn.recv(126)
                        command = command.decode()
                        if command == 'alive':
                            pass
                        else:
                            if command:
                                print(command)
                                self._command['name'] = self._server.clients[conn]['name']
                                self._command['command'] = command
                                self.received_command.emit()
                    except socket.error:
                        print("Client: No Response.")

                    # print('Sending frame')
                    QThread.sleep(0.024)  # 24 frames per second
                    # QThread.sleep(0.5)  # 2 frames per second
                    sent = self._server.send_frame(conn, self._camera.image_byte)
                    # while sent:
                    #     sent = self._server.send_frame(conn, self._camera.image_byte)
            except socket.error:
                self.client_to_remove = conn
                self.client_disconnected.emit()
                print("Client {} disconnected. inside".format(conn))
        self.client_to_remove = conn
        self.client_disconnected.emit()
        print("Client {} disconnected. outside".format(conn))

    def _client_receiver(self, conn):
        while conn:
            if self._command.full():
                self._command.get()
            else:
                try:
                    print('Waiting for command from {name}'.format(name=self._server.clients[conn]['name']))
                    command = conn.recv(1024)
                    self._command.put(
                        self._server.clients[conn]['name'],
                        command)
                    print('Command Received.')
                    self.received_command.emit()
                except socket.error:
                    print("No command")

    @property
    def command(self):
        return self._command

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
    def image_raw(self):  # Returns an un-altered frame
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
        self._zoom = 0
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
            if self._zoom > 0:
                raw_frame = self._zoom_image(raw_frame)
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

    def _zoom_image(self, frame):
        h, w = frame.shape[:2]
        center = ((w / 2), (h / 2))
        zoom = 200
        zoom -= self._zoom
        r = 100.0 / frame.shape[1]
        dim = (100, int(frame.shape[0] * r))
        crop_img = frame[int(center[1]) - zoom:int(center[1]) + zoom,
                         int(center[0]) - zoom:int(center[0]) + zoom]  # Vertical, Horizontal
        crop_img = cv2.resize(crop_img, dim, interpolation=cv2.INTER_AREA)
        return crop_img

    @property
    def zoom(self):
        return self._zoom

    @zoom.setter
    def zoom(self, zoom):
        self._zoom = zoom

    @property
    def started(self):
        return self._started

    @property
    def frame_queue(self):
        return self._frame_queue.get()

    @frame_queue.setter
    def frame_queue(self, frame):
        # retval, buffer = cv2.imencode('.jpg', frame)
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 40]
        retval, buffer = cv2.imencode('.jpg', frame, encode_param)
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
    window.setStyleSheet("color: white;"
                        "background-color: #3a4055;"
                        "selection-color: red;"
                        "selection-background-color: white;")
    # window.setGeometry(0, 0, size.width()/2, size.height()/2)
    window.show()
    sys.exit(app.exec_())
