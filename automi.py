import asyncio
import base64
import functools
import imp
import importlib
import os
import queue
import re
import socket
import threading
import uuid
import json
import webbrowser
from time import sleep

import cv2
import sys

from PyQt5 import QtGui
from PyQt5 import QtCore
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QMainWindow, QApplication, QSizePolicy, QDialog

import server
import automi_ui
import preferences_ui


def check_dependency(dependency):
    return importlib.find_loader(dependency)


if check_dependency('GPIO') is not None:
    from motor import AdaServo, Stepper
else:
    print('Import Error: Unable to import AdaServo, Stepper')


class Window(QMainWindow, automi_ui.Ui_MainWindow):
    _BASE_DIR = os.path.dirname(os.path.realpath(__file__)) + '/'
    _VIDEOS_DIR = _BASE_DIR + 'videos/'
    _IMAGES_DIR = _BASE_DIR + 'images/'
    _VIDEO_NAME = 'video_'
    _VIDEO_EXT = '.avi'
    _IMAGE_NAME = 'image_'
    _IMAGE_EXT = '.jpg'
    _RES = (640, 480)
    _FRAME_RATE = 20.0
    _FOURCC_XVID = cv2.VideoWriter_fourcc(*'XVID')

    print(
        'Base Dir: {base}\nVideo Dir: {vid}\nImage Dir: {img}'.format(base=_BASE_DIR, vid=_VIDEOS_DIR, img=_IMAGES_DIR))

    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self._settings = {}
        self._app_status = True

        self._ip = None
        self._video_port = None
        self._comm_port = None
        self._focus = 0

        self._moving_updown = False
        self._moving_lens = False
        self._recording = False
        self._controlled_by = ''

        self._clients_dic = {}
        self._menus = {}
        self._client_names = []

        # Stepper Motors
        self.updown_motor = None
        self.lens_motor = None
        self.leftright_servo = None
        self.forwardbackward_servo = None
        self.brightness_servo = None

        self._init_settings()
        self._setup()
        self._setup_widgets()
        self._setup_thread_signals()
        self._setup_widget_signals()

    def closeEvent(self, QCloseEvent):
        # self.camera_thread.exit()
        # self.camera.stop()
        #
        # self.video_server_thread.exit()
        # self.video_server.stop()
        #
        # self.command_processing_thread.exit()
        # self.updown_background_thread.ex

        QCloseEvent.accept()
        self._save_settings()
        self._app_status = False
        print('Threads Closed!')
        self.close()

    def _init_settings(self):
        with open(self._BASE_DIR + "settings.json", "r") as read:
            self._settings = json.load(read)

        self._VIDEOS_DIR = self._settings['directories']['videos']
        self._IMAGES_DIR = self._settings['directories']['images']

        self._video_port = self._settings['video_port']
        self._comm_port = self._video_port + 10

    def _save_settings(self):
        print('Closing: Saving settings.')
        with open(self._BASE_DIR + "settings.json", 'w') as file:
            json.dump(self._settings, file, indent=4, sort_keys=True)
        print('Closing: Settings saved.')

    def _setup(self):
        self.camera = Camera(self._settings['camera']['index'])
        self.camera.start()

        self.video_server = server.VideoServer("", self._video_port)
        self.video_server.start()

        self.camera_thread = CameraThread(self.camera)
        self.camera_thread.start()
        self.video_server_thread = VideoServerThread(self.video_server, self.camera_thread)
        self.video_server_thread.start()

        self.servo_thread = ServoThread()
        self.servo_thread.start()
        self.lens_thread = LensThread()
        self.lens_thread.start()

        # Background thread for updown movement of the actuator
        self.updown_worker = UpdownWorker()
        self.updown_background_thread = QtCore.QThread(self)
        self.updown_worker.moveToThread(self.updown_background_thread)
        self.updown_background_thread.started.connect(self.updown_worker.process_command)
        self.updown_background_thread.start()

        try:
            self._ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if
                          not ip.startswith("127.")] or [
                             [(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in
                              [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]
        except:
            print('Please connect to a network.')
        # Create directories if not exists
        dirs = [self._VIDEOS_DIR, self._IMAGES_DIR]
        for dir in dirs:
            print(dir)
            if not os.path.exists(dir):
                print('Creating Dir: ' + dir)
                os.makedirs(dir)
            else:
                print('Dir Already exists ' + dir)

        if check_dependency('GPIO') is not None:
            self.updown_motor = Stepper(
                dir=self._settings['updown_motor']['pins']['dir'],
                step=self._settings['updown_motor']['pins']['step'],
                step_angle=self._settings['updown_motor']['pins']['step_angle'],
                delay=self._settings['updown_motor']['pins']['delay'],
                resolution=self._settings['updown_motor']['pins']['resolution'],
                mode_pins=self._settings['updown_motor']['pins']['mode_pins']
            )  # M0 M1 M2
            print(self.updown_motor)

            self.lens_motor = Stepper(
                dir=self._settings['lens_motor']['pins']['dir'],
                step=self._settings['lens_motor']['pins']['step'],
                step_angle=self._settings['lens_motor']['pins']['step_angle'],
                delay=self._settings['lens_motor']['pins']['delay'],
                resolution=self._settings['lens_motor']['pins']['resolution'],
                mode_pins=self._settings['lens_motor']['pins']['mode_pins']
            )
            print(self.lens_motor)

            # Initialize servo motors
            self.leftright_servo = AdaServo(0, 50)
            self.forwardbackward_servo = AdaServo(2, 50)
            self.brightness_servo = AdaServo(1, 50)

    def _setup_widgets(self):
        self.frame_label.setScaledContents(True)
        self.frame_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        # Set Widget Icons
        self.change_lens_button.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_lens_off.png'
                                                      .format(icons_dir=self._settings['directories']['icons'])
                                                      )))
        self.forward_button.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_forward.png'
                                                  .format(icons_dir=self._settings['directories']['icons'])
                                                  )))
        self.backward_button.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_backward.png'
                                                   .format(icons_dir=self._settings['directories']['icons'])
                                                   )))
        self.left_button.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_left.png'
                                               .format(icons_dir=self._settings['directories']['icons'])
                                               )))
        self.right_button.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_right.png'
                                                .format(icons_dir=self._settings['directories']['icons'])
                                                )))
        self.show_image.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_image_folder.png'
                                              .format(icons_dir=self._settings['directories']['icons'])
                                              )))
        self.show_video.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_video_folder.png'
                                              .format(icons_dir=self._settings['directories']['icons'])
                                              )))
        self.turn_off.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_power_on.png'
                                            .format(icons_dir=self._settings['directories']['icons'])
                                            )))
        self.video_icon.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_record_off.png'
                                              .format(icons_dir=self._settings['directories']['icons'])
                                              )))
        self.camera_icon.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_capture_off.png'
                                               .format(icons_dir=self._settings['directories']['icons'])
                                               )))

        # Set Widget Tooltip
        self.zoom_slider.setToolTip('Zoom')
        self.updown_slider.setToolTip('Up/Down')
        self.brightness_slider.setToolTip('Brightness')
        self.show_video.setToolTip('Open Video Folder')
        self.show_image.setToolTip('Open Image Folder')

        # Set widget max and min values
        self.zoom_slider.setMaximum(self._settings['zoom_slider']['max_position'])
        self.zoom_slider.setMinimum(self._settings['zoom_slider']['min_position'])
        self.updown_slider.setMaximum(self._settings['updown_motor']['max_position'])
        self.updown_slider.setMinimum(self._settings['updown_motor']['min_position'])
        self.brightness_slider.setMaximum(self._settings['brightness_servo']['max_position'])
        self.brightness_slider.setMinimum(self._settings['brightness_servo']['min_position'])

        # Set slider positions
        self.zoom_slider.setSliderPosition(self._settings['zoom_slider']['position'])
        self.updown_slider.setSliderPosition(self._settings['updown_motor']['position'])
        self.brightness_slider.setSliderPosition(self._settings['brightness_servo']['position'])
        self.brightness_slider.setTickInterval(self._settings['brightness_servo']['ticks'])

        # Setup previous position
        self._set_zoom()
        if check_dependency('GPIO') is not None:
            self.brightness_servo.set_angle(self._settings['brightness_servo']['position'])
            self.leftright_servo.set_angle(self._settings['left-right_servo']['position'])
            self.forwardbackward_servo.set_angle(self._settings['forward-backward_servo']['position'])

    def _setup_thread_signals(self):
        # Connect to thread signals. This functions are automatically called when a signal is emitted from the thread
        self.camera_thread.ready_frame.connect(self._update_frame)
        self.video_server_thread.client_accepted.connect(self._update_client_menu)
        self.video_server_thread.client_disconnected.connect(self._remove_client_menu)
        self.video_server_thread.received_command.connect(self._process_sent_command)

        self.servo_thread.move_leftright.connect(self.finished_leftright)
        self.servo_thread.move_forwardbackward.connect(self.finished_forwardbackward)
        self.servo_thread.move_brightness.connect(self.finished_brightness)

        self.lens_thread.started.connect(self.started_lens)
        self.lens_thread.ongoing.connect(self.ongoing_lens)
        self.lens_thread.finished.connect(self.finished_lens)

        self.updown_worker.started.connect(self.started_updown)
        self.updown_worker.ongoing.connect(self.ongoing_updown)
        self.updown_worker.finished.connect(self.finished_updown)

    def _preference_menu(self):
        widget = QDialog(self)
        preferences = PreferencesDialog()
        preferences.setupUi(widget)
        widget.exec_()
        preferences._settings = self._settings
        # preferences.pushButton.clicked.connect(lambda: print('Clicked.'))

    def _setup_widget_signals(self):
        # Connect Menu Actions
        self.action_preferences.triggered.connect(lambda: self._preference_menu())

        # Connect control signals
        self.camera_icon.clicked.connect(self._capture_image)
        self.video_icon.clicked.connect(self._record_video)

        # Close application when clicked
        self.turn_off.clicked.connect(lambda: self._shutdown_computer())
        # Connect to open image folder
        self.show_image.clicked.connect(
            lambda: webbrowser.open(self._BASE_DIR + self._settings['directories']['images']))
        # Connect to open video folder
        self.show_video.clicked.connect(
            lambda: webbrowser.open(self._BASE_DIR + self._settings['directories']['videos']))

        # Clicked Event
        # (widget, command, servo, current_position, step)
        self.left_button.clicked.connect(
            lambda: self.servo_thread.add_command((
                'button',
                'left',
                self.leftright_servo,
                self._settings['left-right_servo']['position'],
                self._settings['left-right_servo']['steps']
            ))
        )
        self.right_button.clicked.connect(
            lambda: self.servo_thread.add_command((
                'button',
                'right',
                self.leftright_servo,
                self._settings['left-right_servo']['position'],
                self._settings['left-right_servo']['steps']
            ))
        )
        self.forward_button.clicked.connect(
            lambda: self.servo_thread.add_command((
                'button',
                'forward',
                self.forward_button,
                self._settings['forward-backward_servo']['position'],
                self._settings['forward-backward_servo']['steps']
            ))
        )
        self.backward_button.clicked.connect(
            lambda: self.servo_thread.add_command((
                'button',
                'backward',
                self.forward_button,
                self._settings['forward-backward_servo']['position'],
                self._settings['forward-backward_servo']['steps']
            ))
        )
        # (motor, lens_index, current_position, p1, p2, p3)
        self.change_lens_button.clicked.connect(
            lambda: self.lens_thread.add_command((
                self.lens_motor,
                self._settings['lens_motor']['index'],
                self._settings['lens_motor']['position']['dynamic'],
                self._settings['lens_motor']['position']['static'][0],
                self._settings['lens_motor']['position']['static'][1],
                self._settings['lens_motor']['position']['static'][2]
            ))
        )

        # Value Changed Event
        self.zoom_slider.valueChanged.connect(self._set_zoom)

        # Released Event
        self.updown_slider.sliderReleased.connect(
            lambda: self.updown_worker.add_command((
                self.updown_motor,
                self.updown_slider.value(),
                self._settings['updown_motor']['position'],
                self._settings['updown_motor']['max_position'],
                self._settings['updown_motor']['min_position']
            ))
        )
        self.brightness_slider.sliderReleased.connect(
            lambda: self.servo_thread.add_command((
                'slider',
                'brightness',
                self.brightness_servo,
                self.brightness_slider.value(),
                0
            ))
        )

    def _reset_server(self):
        print('Resetting server...')
        # del self.video_server
        # self.video_server = server.VideoServer("", self._video_port)
        # # self.video_server.start()
        #
        # self.video_server_thread = VideoServerThread(self.video_server, self.camera_thread)
        # # self.video_server_thread.start()
        try:
            self._ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if
                  not ip.startswith("127.")] or [
                  [(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in
                  [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]
        except:
            self._ip = ""
            print('Please connect to a network.')

        self.video_server.reset((self._ip, self._video_port))

    def _shutdown_computer(self):
        self.close()
        os.system("shutdown -P now")

    def _update_client_menu(self):
        self.connected_devices_menu.clear()
        for client in self.video_server.clients:
            name = self.video_server.clients[client]['name']
            self._client_names.append(name)
            self._clients_dic[name] = lambda: self._grant_control(name)
            menu = self.connected_devices_menu.addMenu(name)
            menu.addAction('Grant Control', functools.partial(self._grant_control, name))
            menu.addAction('Remove Control').triggered.connect(self._remove_control)

    def _remove_client_menu(self):
        conn = self.video_server_thread.client_to_remove
        if self._controlled_by == self.video_server.clients[conn]['name']:
            del self._clients_dic[self._controlled_by]
            self._controlled_by = ""
        self.video_server.clients = conn
        self._update_client_menu()

    def _grant_control(self, client_name):
        print('Granting control to ' + client_name)
        self._controlled_by = client_name

    def _remove_control(self):
        self._controlled_by = ''

    def _process_sent_command(self):
        name = self.video_server_thread.command['name']
        command = self.video_server_thread.command['command']

        if self._controlled_by == name:
            command = command.split(":")
            command_type = command[0]

            if command_type == 'zoom':
                command_value = int(command[1])
                self.camera.zoom = command_value
                self.zoom_slider.setValue(command_value)
            elif command_type == 'brightness':
                command_value = int(command[1])
                self.brightness_slider.setValue(command_value)
            elif command_type == 'forward':
                self.servo_thread.add_command((
                    'button',
                    'forward',
                    self.forward_button,
                    self._settings['forward-backward_servo']['position'],
                    self._settings['forward-backward_servo']['steps']
                ))
            elif command_type == 'backward':
                self.servo_thread.add_command((
                    'button',
                    'backward',
                    self.forward_button,
                    self._settings['forward-backward_servo']['position'],
                    self._settings['forward-backward_servo']['steps']
                ))
            elif command_type == 'left':
                self.servo_thread.add_command((
                    'button',
                    'left',
                    self.leftright_servo,
                    self._settings['left-right_servo']['position'],
                    self._settings['left-right_servo']['steps']
                ))
            elif command_type == 'right':
                self.servo_thread.add_command((
                    'button',
                    'right',
                    self.leftright_servo,
                    self._settings['left-right_servo']['position'],
                    self._settings['left-right_servo']['steps']
                ))
            elif command_type == 'up':
                # if self._settings['updown_motor']['position'] < self._settings['updown_motor']['max_position']:
                #     self._settings['updown_motor']['position'] += 1
                #     self.updown_slider.setValue(self._settings['updown_motor']['position'])
                #     self.updown_motor.rotate('ccw')
                self.updown_worker.add_command((
                    self.updown_motor,
                    self._settings['updown_motor']['position'] + 1,
                    self._settings['updown_motor']['position'],
                    self._settings['updown_motor']['max_position'],
                    self._settings['updown_motor']['min_position']
                ))
            elif command_type == 'down':
                # if self._settings['updown_motor']['position'] > self._settings['updown_motor']['min_position']:
                #     self._settings['updown_motor']['position'] -= 1
                #     self.updown_slider.setValue(self._settings['updown_motor']['position'])
                #     self.updown_motor.rotate('cw')
                self.updown_worker.add_command((
                    self.updown_motor,
                    self._settings['updown_motor']['position'] - 1,
                    self._settings['updown_motor']['position'],
                    self._settings['updown_motor']['max_position'],
                    self._settings['updown_motor']['min_position']
                ))
            else:
                print('Command{cmd} is not yet available'.format(cmd=command_type))
        else:
            print("User:{name} is not permitted to control device.".format(name=name))

    # def _move_stage(self, direction, action):
    #     setting_name = {
    #         "lr": ['left-right_servo', self.leftright_servo],
    #         "fb": ['forward-backward_servo', self.forwardbackward_servo],
    #     }
    #     servo = setting_name[direction][1]
    #     pre_position = self._settings[setting_name[direction][0]]['position']
    #     post_position = pre_position
    #     step = self._settings[setting_name[direction][0]]['steps']
    #
    #     if action == 'inc' and post_position < 180:
    #         post_position += step
    #
    #     elif action == 'dec' and post_position > 0:
    #         post_position -= step
    #
    #     servo.set_angle(post_position)
    #     self._settings[setting_name[direction][0]]['position'] = post_position
    #
    # def _move_lens(self):
    #     self._moving_lens = not self._moving_lens
    #     print('Changing Lens: {}'.format(self._moving_lens))
    #
    #     if self._moving_lens:
    #         self.change_lens_button.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_lens_on.png'
    #                                                       .format(icons_dir=self._settings['directories']['icons'])
    #                                                       )))
    #         lens_index = self._settings['lens_motor']['index']
    #         current_position = self._settings['lens_motor']['position']['dynamic']
    #         if lens_index == 0:
    #             # Rotate Stepper To next lens
    #             print('Changing Lens: 0->1')
    #             while self._moving_lens and current_position < \
    #                     self._settings['lens_motor']['position']['static'][1]:  # 2000
    #                 current_position += 1
    #                 # self.lens_motor.step_rotate('cw')
    #                 sleep(0.5)
    #                 self._settings['lens_motor']['position']['dynamic'] = current_position
    #             if self._moving_lens:
    #                 lens_index = 1
    #                 self._moving_lens = False
    #                 print('Cycle complete')
    #             else:
    #                 print('Cycle incomplete.')
    #
    #             print('Current Position: {} - Expected Position: {}'.format(
    #                 current_position,
    #                 self._settings['lens_motor']['position']['static'][1])
    #             )
    #
    #         elif lens_index == 1:
    #             # Rotate Stepper clockwise going to lens 2
    #             print('Changing Lens: 1->2')
    #             while self._moving_lens and current_position < \
    #                     self._settings['lens_motor']['position']['static'][2]:  # 4000
    #                 current_position += 1
    #                 # print('Current Position: {}'.format(current_position))
    #                 # self.lens_motor.step_rotate('cw')
    #                 sleep(0.5)
    #                 self._settings['lens_motor']['position']['dynamic'] = current_position
    #
    #             if self._moving_lens:
    #                 lens_index = 2
    #                 self._moving_lens = False
    #                 print('Cycle complete')
    #             else:
    #                 print('Cycle incomplete.')
    #
    #             print('Current Position: {} - Expected Position: {}'.format(
    #                 current_position,
    #                 self._settings['lens_motor']['position']['static'][2])
    #             )
    #         elif lens_index == 2:
    #             # Rotate Stepper counter clockwise returning to lens 3
    #             print('Changing Lens: 2->0')
    #             while self._moving_lens and current_position > \
    #                     self._settings['lens_motor']['position']['static'][0]:  # 0
    #                 current_position -= 1
    #                 # print('Current Position: {}'.format(current_position))
    #                 # self.lens_motor.step_rotate('ccw')
    #                 sleep(0.5)
    #                 self._settings['lens_motor']['position']['dynamic'] = current_position
    #
    #             if self._moving_lens:
    #                 lens_index = 0
    #                 self._moving_lens = False
    #                 print('Cycle complete')
    #             else:
    #                 print('Cycle incomplete.')
    #             print('Current Position: {} - Expected Position: {}'.format(
    #                 current_position,
    #                 self._settings['lens_motor']['position']['static'][0])
    #             )
    #
    #         self.change_lens_button.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_lens_off.png'
    #                                                       .format(icons_dir=self._settings['directories']['icons'])
    #                                                       )))
    #         self._settings['lens_motor']['index'] = lens_index
    #         print('Lens Index: ' + str(lens_index))
    #     else:
    #         print('Stopping lens changing.')
    #         self.change_lens_button.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_lens_off.png'
    #                                                       .format(icons_dir=self._settings['directories']['icons'])
    #                                                       )))

    def _set_zoom(self):  # Digitally set zoom on the image depending on slider value
        self.camera.zoom = self.zoom_slider.value()
        self._settings['zoom_slider']['position'] = self.zoom_slider.value()

    # def _move_brightness(self):  # Controls the angle of the servo for the diaphragm to andjust led brightness
    #     angle = self.brightness_slider.value()
    #     self.brightness_servo.set_angle(angle)
    #     self._settings['brightness_servo']['position'] = angle
    #
    # def _move_updown(self):
    #     steps = None
    #     direction = None
    #     self._moving_updown = not self._moving_updown
    #     if self._moving_updown:
    #         new_position = self.updown_slider.value()
    #         print('Setting New Position: ' + str(new_position))
    #         current_position = self._settings['updown_motor']['position']
    #         previous_position = current_position
    #         self.updown_slider.setStyleSheet('background: rgb(204, 0, 14);')
    #         if new_position >= current_position:
    #             direction = "up"
    #             steps = new_position - current_position
    #         elif new_position <= current_position:
    #             direction = "down"
    #             steps = current_position - new_position
    #
    #         for step in range(steps):
    #             if self._moving_updown and self._app_status and direction == "up" and current_position < \
    #                     self._settings['updown_motor']['max_position']:
    #                 current_position += 1
    #                 # self.updown_motor.rotate
    #                 sleep(0.5)
    #                 self._settings['updown_motor']['position'] = current_position
    #                 print('Current Position(Up): ' + str(current_position))
    #             elif self._moving_updown and self._app_status and direction == "down" and current_position > \
    #                     self._settings['updown_motor']['min_position']:
    #                 current_position -= 1
    #                 # self.updown_motor.rotate('cw')
    #                 sleep(0.5)
    #                 self._settings['updown_motor']['position'] = current_position
    #                 print('Current Position(Down): ' + str(current_position))
    #             else:
    #                 print("Limit Reach/Cancelled")
    #                 break
    #
    #         if self._moving_updown:
    #             self._moving_updown = False
    #             print('Cycle complete.')
    #             if direction == 'up':
    #                 print('Current Position: {} - Expected Position: {}'.format(current_position,
    #                                                                             previous_position + steps))
    #             else:
    #                 print('Current Position: {} - Expected Position: {}'.format(current_position,
    #                                                                             previous_position - steps))
    #         else:
    #             print('Cycle incomplete')
    #             if direction == 'up':
    #                 print('Current Position: {} - Expected Position: {}'.format(current_position,
    #                                                                             previous_position + steps))
    #             else:
    #                 print('Current Position: {} - Expected Position: {}'.format(current_position,
    #                                                                             previous_position - steps))
    #
    #     self.updown_slider.setStyleSheet('background: #565e7c;')

    def _record_video(self):
        if not self._recording:
            self.uniq_id = str(uuid.uuid4().hex)
        self._recording = not self._recording

        if self._recording:
            self.writer = cv2.VideoWriter('{dir}{name}{uid}{ext}'.format(
                dir=self._BASE_DIR + self._VIDEOS_DIR,
                name=self._VIDEO_NAME,
                ext=self._VIDEO_EXT,
                uid=self.uniq_id
            ),
                self._FOURCC_XVID,
                self._FRAME_RATE,
                self._RES
            )

            self.statusbar.showMessage(
                "Recording Video: {dir}{name}{uid}{ext}".format(dir=self._VIDEOS_DIR, name=self._VIDEO_NAME,
                                                                ext=self._VIDEO_EXT, uid=self.uniq_id))
            self.video_icon.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_record_on.png'
                                                  .format(icons_dir=self._settings['directories']['icons'])
                                                  )))

        else:
            self.statusbar.showMessage(
                "Done Recording Video: {name}{uid}{ext}".format(name=self._VIDEO_NAME, ext=self._VIDEO_EXT,
                                                                uid=self.uniq_id))
            self.video_icon.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_record_off.png'
                                                  .format(icons_dir=self._settings['directories']['icons'])
                                                  )))

    def _capture_image(self):
        uniq_id = str(uuid.uuid4().hex)
        self.camera_icon.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_capture_on.png'
                                               .format(icons_dir=self._settings['directories']['icons'])
                                               )))
        if self.camera.started:
            frame = self.camera_thread.image_raw

            cv2.imwrite(
                '{dir}{name}_{id}.png'.format(dir=self._BASE_DIR + self._IMAGES_DIR, name=self._IMAGE_NAME, id=uniq_id),
                frame)
            self.statusbar.showMessage("Saved Image: {0}_{1}.png".format(self._IMAGE_NAME, uniq_id))
        else:
            self.camera_icon.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_capture_off.png'
                                                   .format(icons_dir=self._settings['directories']['icons'])
                                                   )))
            print('CameraErr: Camera is turned off.')
        self.camera_icon.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_capture_off.png'
                                               .format(icons_dir=self._settings['directories']['icons'])
                                               )))

    def _update_frame(self):
        frame = self.camera_thread.image_raw
        self._focus = cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_size = 0.8
        thickness = 1
        color = (255, 255, 255)

        if self.camera.zoom == 0:
            location = (4, 20)
            text = "Connection: {ip}:{port_1}".format(ip=self._ip, port_1=self._video_port)
            cv2.putText(frame, text, location, font, font_size, color, thickness, cv2.LINE_AA)
            location = (4, 45)
            text = "Controller: {control}".format(control=self._controlled_by)
            cv2.putText(frame, text, location, font, font_size, color, thickness, cv2.LINE_AA)
            location = (4, 70)
            text = f"Blurred: {self._focus}" if (
                        self._focus < self._settings['camera']['blur']['threshold']) else f"Not Blurred: {self._focus}"
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

    def _auto_focus(self):
        current_position = self._settings['updown_motor']['position']
        threshold = self._settings['camera']['blur']['threshold']
        max_position = self._settings['updown_motor']['max_position']
        min_position = self._settings['updown_motor']['min_position']
        topped = False
        bottomed = False
        while self._focus < threshold:
            # Go down first then up until image is not blurred
            if not topped and self._app_status and current_position < max_position and not current_position == max_position:  # Direction: Up
                current_position += 1
                # self.updown_motor.rotate('ccw')
                sleep(0.5)
                self._settings['updown_motor']['position'] = current_position
                if current_position == max_position:
                    topped = True
            elif not bottomed and self._app_status and current_position > min_position and not current_position == min_position:  # Direction: Down
                current_position -= 1
                # self.updown_motor.rotate('cw')
                sleep(0.5)
                self._settings['updown_motor']['position'] = current_position
                if current_position == min_position:
                    bottomed = True

    @pyqtSlot(int)
    def finished_leftright(self, position):
        self._settings['left-right_servo']['position'] = position

    @pyqtSlot(int)
    def finished_forwardbackward(self, position):
        self._settings['forward-backward_servo']['position'] = position

    @pyqtSlot(int)
    def finished_brightness(self, position):
        self._settings['brightness_servo']['position'] = position

    @pyqtSlot()
    def started_lens(self):
        self.change_lens_button.clicked.disconnect()
        self.change_lens_button.clicked.connect(lambda: self.lens_thread.stop_command())
        self.change_lens_button.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_lens_on.png'
                                                      .format(icons_dir=self._settings['directories']['icons'])
                                                      )))

    @pyqtSlot(int, int)
    def ongoing_lens(self, index, position):
        self._settings['lens_motor']['index'] = index
        self._settings['lens_motor']['position']['dynamic'] = position
        print(f'Lens -> Current Position: {position} at Lens: {index}')

    @pyqtSlot(int, int)
    def finished_lens(self, index, position):
        self.change_lens_button.clicked.disconnect()
        self.change_lens_button.clicked.connect(
            lambda: self.lens_thread.add_command((
                self.lens_motor,
                self._settings['lens_motor']['index'],
                self._settings['lens_motor']['position']['dynamic'],
                self._settings['lens_motor']['position']['static'][0],
                self._settings['lens_motor']['position']['static'][1],
                self._settings['lens_motor']['position']['static'][2]
            ))
        )
        self._settings['lens_motor']['index'] = index
        self._settings['lens_motor']['position']['dynamic'] = position
        self.change_lens_button.setIcon(QIcon(QPixmap(self._BASE_DIR + '{icons_dir}/icon_lens_off.png'
                                                      .format(icons_dir=self._settings['directories']['icons'])
                                                      )))
        print(f'Saving Current Position: {position}')
        print(f'Lens -> Lens Index: {index}')

    @pyqtSlot()
    def started_updown(self):
        self.updown_slider.setStyleSheet('background: rgb(204, 0, 14);')
        print('started_updown_process: Updown movement started.')
        self.updown_slider.sliderReleased.disconnect()
        self.updown_slider.sliderPressed.connect(lambda: self.updown_worker.stop_command())

    @pyqtSlot(int)
    def ongoing_updown(self, position):
        print(f'Updown -> Current Position: {position}')
        self._settings['updown_motor']['position'] = position

    @pyqtSlot(int)
    def finished_updown(self, position):
        self._settings['updown_motor']['position'] = position
        print(f'Saving last position(updown): {position}')
        self.updown_slider.sliderPressed.connect(lambda: self.updown_worker.stop_command())
        self.updown_slider.sliderPressed.disconnect()
        self.updown_slider.sliderReleased.connect(lambda: self.updown_worker.add_command((
            self.updown_slider.value(),
            self._settings['updown_motor']['position'],
            self._settings['updown_motor']['max_position'],
            self._settings['updown_motor']['min_position']
        )))
        self.updown_slider.setStyleSheet('background: #565e7c;')


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


class LensThread(QThread):
    started = pyqtSignal()
    ongoing = pyqtSignal(int, int)
    finished = pyqtSignal(int, int)

    def __init__(self):
        QtCore.QThread.__init__(self)
        self.commands_queue = queue.Queue(1)
        self.moving_lens = True
        self.running = True

    def __del__(self):
        self.wait()
        print("Closing Lens Thread.")

    def add_command(self, cmd):
        self.commands_queue.put(cmd)
        self.moving_lens = True

    def stop_command(self):
        self.moving_lens = False

    def run(self):
        while self.running:
            (motor, lens_index, current_position, p1, p2, p3) = self.commands_queue.get()
            self.started.emit()

            if lens_index == 0:
                # Rotate Stepper To next lens
                print('Changing Lens: 0->1')
                while self.moving_lens and current_position < p2:  # 2000
                    current_position += 1
                    if check_dependency('GPIO') is not None:
                        self.lens_motor.step_rotate('cw')
                    else:
                        sleep(0.5)
                    self.ongoing.emit(lens_index, current_position)

                if self.moving_lens:
                    lens_index = 1
                    self.moving_lens = False
                    print('Cycle complete')
                else:
                    print('Cycle incomplete.')
                    print(f'Current Position: {current_position} - Expected Position: {p2}')

            elif lens_index == 1:
                # Rotate Stepper clockwise going to lens 2
                print('Changing Lens: 1->2')
                while self.moving_lens and current_position < p3:  # 4000
                    current_position += 1
                    if check_dependency('GPIO') is not None:
                        self.lens_motor.step_rotate('cw')
                    else:
                        sleep(0.5)
                    self.ongoing.emit(lens_index, current_position)

                if self.moving_lens:
                    lens_index = 2
                    self.moving_lens = False
                    print('Cycle complete')
                else:
                    print('Cycle incomplete.')
                    print(f'Current Position: {current_position} - Expected Position: {p3}')

            elif lens_index == 2:
                # Rotate Stepper counter clockwise returning to lens 3
                print('Changing Lens: 2->0')
                while self.moving_lens and current_position > p1:  # 0
                    current_position -= 1
                    if check_dependency('GPIO') is not None:
                        self.lens_motor.step_rotate('ccw')
                    else:
                        sleep(0.5)
                    self.ongoing.emit(lens_index, current_position)

                if self.moving_lens:
                    lens_index = 0
                    self.moving_lens = False
                    print('Cycle complete')
                else:
                    print('Cycle incomplete.')
                    print(f'Current Position: {current_position} - Expected Position: {p1}')
            self.finished.emit(lens_index, current_position)


class UpdownWorker(QThread):
    started = QtCore.pyqtSignal()
    ongoing = QtCore.pyqtSignal(int)
    finished = QtCore.pyqtSignal(int)

    moving = False
    commands_queue = queue.Queue(1)

    def add_command(self, cmd):
        self.commands_queue.put(cmd)
        self.moving = True

    def stop_command(self):
        self.moving = False
        print(f'self.moving = {self.moving}')

    @QtCore.pyqtSlot()
    def process_command(self):
        steps = None
        direction = None

        while True:
            (motor, new_position, current_position, max_position, min_position) = self.commands_queue.get()
            self.started.emit()
            print(f'UpdownWorker -> process_command: Setting New Position: {new_position}')
            if new_position >= current_position:
                direction = "up"
                steps = new_position - current_position
            elif new_position <= current_position:
                direction = "down"
                steps = current_position - new_position

            for step in range(steps):
                if self.moving and direction == "up" and current_position < \
                        max_position:
                    current_position += 1
                    if check_dependency('GPIO') is not None:
                        motor.rotate('ccw')
                    else:
                        sleep(1)
                    self.ongoing.emit(current_position)
                elif self.moving and direction == "down" and current_position > \
                        min_position:
                    current_position -= 1
                    if check_dependency('GPIO') is not None:
                        motor.rotate('cw')
                    else:
                        sleep(1)
                    self.ongoing.emit(current_position)
                else:
                    if current_position == max_position:
                        print("UpdownWoker -> process_command: Upper Limit Reached.")
                    elif current_position ==  min_position:
                        print("UpdownWoker -> process_command: Lower Limit Reached.")
                    else:
                        print("UpdownWoker -> process_command: Process Canceled.")
                    self.finished.emit(current_position)
                    break
            self.finished.emit(current_position)


class ServoThread(QtCore.QThread):
    move_leftright = pyqtSignal(int)
    move_forwardbackward = pyqtSignal(int)
    move_brightness = pyqtSignal(int)

    def __init__(self):
        QtCore.QThread.__init__(self)
        self.commands_queue = queue.Queue(1)
        self.processing = True

    def __del__(self):
        self.wait()
        print("Closing Servo Thread.")

    def add_command(self, cmd):
        self.commands_queue.put(cmd)

    def run(self):
        while self.processing:
            # Widgets [button, slider]
            (widget, command, servo, current_position, step) = self.commands_queue.get()

            if widget == 'button':
                if command == 'left':
                    current_position += step
                    if check_dependency('GPIO') is not None:
                        servo.set_angle(current_position)
                    self.move_left.emit(current_position)
                elif command == 'right':
                    current_position -= step
                    if check_dependency('GPIO') is not None:
                        servo.set_angle(current_position)
                    self.move_right.emit(current_position)
                elif command == 'forward':
                    current_position += step
                    if check_dependency('GPIO') is not None:
                        servo.set_angle(current_position)
                    self.move_forward.emit(current_position)
                elif command == 'backward':
                    current_position -= step
                    if check_dependency('GPIO') is not None:
                        servo.set_angle(current_position)
                    self.move_backward.emit(current_position)
                else:
                    print('Command not supported!')
            elif widget == 'slider':
                if command == 'brightness':
                    if check_dependency('GPIO') is not None:
                        servo.set_angle(current_position)
                    self.move_brightness.emit(current_position)
                else:
                    print('Command not supported!')
            else:
                print('Widget not supported!')


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
                # print('Camera: Adding frame to queue')
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
            return ok, frame
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


class PreferencesDialog(QDialog, preferences_ui.Ui_Dialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self._settings = {}
        self.pushButton.clicked(lambda: self.click_me())
        print('Initialized.')

    def click_me(self):
        print('You clicked me!')
        print(self._settings)

if __name__ == "__main__":
    app = QApplication(sys.argv)
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
