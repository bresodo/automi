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
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QSettings
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QMainWindow, QApplication, QSizePolicy, QDialog

import server
import automi_ui
import preferences_ui


def check_dependency(dependency):
    return importlib.find_loader(dependency)


def convert(item):
    try:
        print('item -> int')
        item = int(item)
        return item
    except ValueError:
        print('Unable to convert. Invalid input')
        try:
            print('item -> float')
            item = float(item)
            return item
        except ValueError:
            print('Unable to convert. Invalid input')
            try:
                print('item -> str')
                item = str(item)
                return item
            except ValueError:
                print('Unable to convert. Invalid input')


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
        self._application_settings = QSettings()
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
        self._application_settings.setValue('automi_settings', self._settings)

        print(self._application_settings.value('automi_settings'))

        self._VIDEOS_DIR = self._settings['directories']['videos']
        self._IMAGES_DIR = self._settings['directories']['images']

        self._VIDEO_NAME = self._settings['camera']['names']['video']
        self._IMAGE_NAME = self._settings['camera']['names']['image']

        self._video_port = self._settings['server']['video_port']
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

        self.servomotor_thread = ServoMotorThread()
        self.servomotor_thread.start()

        self.servo_thread = ServoThread()
        # self.servo_thread.start()
        self.lens_thread = LensThread()
        # self.lens_thread.start()
        self.autofocus_thread = AutofocusThread()
        # self.autofocus_thread.start()

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

        self.servomotor_thread.move_leftright.connect(self.finished_leftright)
        self.servomotor_thread.move_forwardbackward.connect(self.finished_forwardbackward)
        self.servomotor_thread.move_brightness.connect(self.finished_brightness)

        self.servomotor_thread.started_lens.connect(self.started_lens)
        self.servomotor_thread.ongoing_lens.connect(self.ongoing_lens)
        self.servomotor_thread.finished_lens.connect(self.finished_lens)

        self.servomotor_thread.started_updown.connect(self.started_updown)
        self.servomotor_thread.ongoing_updown.connect(self.ongoing_updown)
        self.servomotor_thread.finished_updown.connect(self.finished_updown)

        self.autofocus_thread.started.connect(self.started_autofocus)
        self.autofocus_thread.ongoing.connect(self.ongoing_autofocus)
        self.autofocus_thread.finished.connect(self.finished_autofocus)


    def _setup_widget_signals(self):
        # Connect Menu Actions
        self.action_preferences.triggered.connect(lambda: self._menu_preference())
        # (self.current_position, self.focus, self.threshold, self.max_position, self.min_position)
        self.action_autofocus.triggered.connect(
            lambda: self.autofocus_thread.add_command((
                self._settings['updown_motor']['position'],
                self._focus,
                self._settings['camera']['blur']['threshold'],
                self._settings['updown_motor']['max_position'],
                self._settings['updown_motor']['min_position']

            ))
        )

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
            lambda: self.servomotor_thread.start_lrfb({
                'widget': 'button',
                'command': 'left',
                'servo': self.forward_button,
                'current_position': self._settings['left-right_servo']['position'],
                'step': self._settings['left-right_servo']['steps']
            })
        )
        self.right_button.clicked.connect(
            lambda: self.servomotor_thread.start_lrfb({
                'widget': 'button',
                'command': 'right',
                'servo': self.forward_button,
                'current_position': self._settings['left-right_servo']['position'],
                'step': self._settings['left-right_servo']['steps']
            })
        )
        self.forward_button.clicked.connect(
            lambda: self.servomotor_thread.start_lrfb({
                'widget': 'button',
                'command': 'forward',
                'servo': self.forward_button,
                'current_position': self._settings['forward-backward_servo']['position'],
                'step': self._settings['forward-backward_servo']['steps']
            })
        )
        self.backward_button.clicked.connect(
            lambda: self.servomotor_thread.start_lrfb({
                'widget': 'button',
                'command': 'backward',
                'servo': self.forward_button,
                'current_position': self._settings['forward-backward_servo']['position'],
                'step': self._settings['forward-backward_servo']['steps']
            })
        )
        # (motor, lens_index, current_position, p1, p2, p3)
        self.change_lens_button.clicked.connect(
            lambda: self.servomotor_thread.start_lens({
                'motor': self.lens_motor,
                'lens_index': self._settings['lens_motor']['index'],
                'current_position': self._settings['lens_motor']['position']['dynamic'],
                'p1': self._settings['lens_motor']['position']['static'][0],
                'p2': self._settings['lens_motor']['position']['static'][1],
                'p3': self._settings['lens_motor']['position']['static'][2]
            })
        )

        # Value Changed Event
        self.zoom_slider.valueChanged.connect(self._set_zoom)

        # Released Event
        self.updown_slider.sliderReleased.connect(
            lambda: self.servomotor_thread.start_updown({
                'motor': self.updown_motor,
                'new_position': self.updown_slider.value(),
                'current_position': self._settings['updown_motor']['position'],
                'max_position': self._settings['updown_motor']['max_position'],
                'min_position': self._settings['updown_motor']['min_position']
            })
        )
        # widget, command, servo, current_position,
        self.brightness_slider.sliderReleased.connect(
            lambda: self.servomotor_thread.start_lrfb({
                'widget': 'slider',
                'command': 'brightness',
                'servo': self.brightness_servo,
                'current_position': self.brightness_slider.value(),
                'step': 0
            })
        )

    def _menu_preference(self):
        widget = QDialog(self)
        preferences = PreferencesDialog(self)
        preferences.setupUi(widget)
        # Change/Add Widget here update from windows
        settings_list = {
            'camera': {'index': 'int', 'blur.threshold': 'int',
                       'names.image': 'string', 'names.video': 'string'
            },
            # 'brightness_servo': {'max_position':'int', 'min_position':'int',
            #                      'pin':'int', 'position':'int', 'ticks':'int',
            # },
            # 'directories': {'icons': 'str', 'images': 'str', 'videos': 'str', },
            # 'forward-backward_servo': {'pin': 'int', 'position': 'int', 'steps': 'int', },
            # 'left-right_servo': {'pin': 'int', 'position': 'int', 'steps': 'int', },
            # 'lens_motor': {'index': 'int', 'pins.delay': 'float', 'pins.dir': 'int',
            #                'pins.mode_pins.0': 'int', 'pins.mode_pins.1': 'int', 'pins.mode_pins.2': 'int',
            #                'resolution': 'int', 'step': 'int', 'step_angle': 'int',
            #                'position.dynamic': 'int', 'position.static.0': 'int', 'position.static.1': 'int',
            #                'position.static.2': 'int',
            # },
            # 'updown_motor': {'max_position':'int', 'min_position':'int',
            #                  'pins.delay': 'float', 'pins.dir': 'int',
            #                  'pins.mode_pins.0': 'int', 'pins.mode_pins.1': 'int', 'pins.mode_pins.2': 'int',
            #                  'resolution': 'int', 'step': 'int', 'step_angle': 'int',
            #                  'position': 'int',
            # },
            # 'server': {'video_port': 'int', },
            # 'zoom_slider': {'max_position':'int', 'min_position':'int', 'position': 'int'},
        }
        settings_widget = {
            'camera': (preferences.camera_index, preferences.blur_threshold, preferences.name_image, preferences.name_video),
        }

        index = 0
        for setting, items in settings_list.items():
            print(f'{setting}: {items}')
            for item, type in items.items():
                results = item.split('.')
                len_results = len(results)
                if len_results == 1:
                    settings_widget[setting][index].setText(str(self._settings[setting][results[0]]))
                elif len_results == 2:
                    settings_widget[setting][index].setText(str(self._settings[setting][results[0]][results[1]]))

                index += 1
        # preferences.camera_index.setText(str(self._settings['camera']['index']))
        # preferences.blur_threshold.setText(str(self._settings['camera']['blur']['threshold']))
        # preferences.name_image.setText(self._settings['camera']['names']['image'])
        # preferences.name_video.setText(self._settings['camera']['names']['video'])
        preferences.buttonBox.accepted.connect(preferences.save_settings)
        preferences._settings = self._settings
        preferences.saved_settings.connect(self.change_settings)

        widget.exec_()

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
                self.servomotor_thread.start_lrfb({
                    'widget': 'slider',
                    'command': 'brightness',
                    'servo': self.brightness_servo,
                    'current_position': self.brightness_slider.value(),
                    'step': 0
                })
                self.brightness_slider.setValue(command_value)
            elif command_type == 'forward':
                self.servomotor_thread.start_lrfb({
                    'widget': 'button',
                    'command': 'forward',
                    'servo': self.forward_button,
                    'current_position': self._settings['forward-backward_servo']['position'],
                    'step': self._settings['forward-backward_servo']['steps']
                })
            elif command_type == 'backward':
                self.servomotor_thread.start_lrfb({
                    'widget': 'button',
                    'command': 'backward',
                    'servo': self.forward_button,
                    'current_position': self._settings['forward-backward_servo']['position'],
                    'step': self._settings['forward-backward_servo']['steps']
                })
            elif command_type == 'left':
                self.servomotor_thread.start_lrfb({
                    'widget': 'button',
                    'command': 'left',
                    'servo': self.forward_button,
                    'current_position': self._settings['left-right_servo']['position'],
                    'step': self._settings['left-right_servo']['steps']
                })
            elif command_type == 'right':
                self.servomotor_thread.start_lrfb({
                    'widget': 'button',
                    'command': 'right',
                    'servo': self.forward_button,
                    'current_position': self._settings['left-right_servo']['position'],
                    'step': self._settings['left-right_servo']['steps']
                })
            elif command_type == 'up':
                # if self._settings['updown_motor']['position'] < self._settings['updown_motor']['max_position']:
                #     self._settings['updown_motor']['position'] += 1
                #     self.updown_slider.setValue(self._settings['updown_motor']['position'])
                #     self.updown_motor.rotate('ccw')
                self.servomotor_thread.start_updown({
                    'motor': self.updown_motor,
                    'new_position': self._settings['updown_motor']['position'] + 1,
                    'current_position': self._settings['updown_motor']['position'],
                    'max_position': self._settings['updown_motor']['max_position'],
                    'min_position': self._settings['updown_motor']['min_position']
                })
            elif command_type == 'down':
                # if self._settings['updown_motor']['position'] > self._settings['updown_motor']['min_position']:
                #     self._settings['updown_motor']['position'] -= 1
                #     self.updown_slider.setValue(self._settings['updown_motor']['position'])
                #     self.updown_motor.rotate('cw')
                self.servomotor_thread.start_updown({
                    'motor': self.updown_motor,
                    'new_position': self._settings['updown_motor']['position'] - 1,
                    'current_position': self._settings['updown_motor']['position'],
                    'max_position': self._settings['updown_motor']['max_position'],
                    'min_position': self._settings['updown_motor']['min_position']
                })
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
                '{dir}{name}{id}.png'.format(dir=self._BASE_DIR + self._IMAGES_DIR, name=self._IMAGE_NAME, id=uniq_id),
                frame)
            self.statusbar.showMessage("Saved Image: {}{}.png".format(self._IMAGE_NAME, uniq_id))
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
            # location = (4, 70)
            # text = "Blurred: {}".format(self._focus) if (
            #             self._focus < self._settings['camera']['blur']['threshold']) else "Not Blurred: {}".format(self._focus)
            # cv2.putText(frame, text, location, font, font_size, color, thickness, cv2.LINE_AA)
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

        focus_prev = self._focus
        focus_diff = focus_prev - self._focus
        print('Auto focusing')
        while self._focus < threshold:

            print(f'Focus Difference: {focus_diff}')
            if focus_diff >= 5:
                pass
            # Go down first then up until image is not blurred
            # if not topped and self._app_status and current_position < max_position and not current_position == max_position:  # Direction: Up
            #     current_position += 1
            #     if check_dependency('GPIO') is not None:
            #         self.updown_motor.rotate('ccw')
            #     sleep(0.5)
            #     self._settings['updown_motor']['position'] = current_position
            #     if current_position == max_position:
            #         topped = True
            # elif not bottomed and self._app_status and current_position > min_position and not current_position == min_position:  # Direction: Down
            #     current_position -= 1
            #     if check_dependency('GPIO') is not None:
            #         self.updown_motor.rotate('cw')
            #     sleep(0.5)
            #     self._settings['updown_motor']['position'] = current_position
            #     if current_position == min_position:
            #         bottomed = True

    @pyqtSlot(int)
    def finished_leftright(self, position):
        self._settings['left-right_servo']['position'] = position
        print('Left-Right: Position({})'.format(position))

    @pyqtSlot(int)
    def finished_forwardbackward(self, position):
        self._settings['forward-backward_servo']['position'] = position
        print('Forward-Backward: Position({})'.format(position))

    @pyqtSlot(int)
    def finished_brightness(self, position):
        self._settings['brightness_servo']['position'] = position
        print('Brightness: Position({})'.format(position))

    @pyqtSlot()
    def started_lens(self):
        self.change_lens_button.clicked.disconnect()
        self.change_lens_button.clicked.connect(lambda: self.servomotor_thread.stop_lens())
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
            lambda: self.servomotor_thread.start_lens({
                'motor': self.lens_motor,
                'lens_index': self._settings['lens_motor']['index'],
                'current_position': self._settings['lens_motor']['position']['dynamic'],
                'p1': self._settings['lens_motor']['position']['static'][0],
                'p2': self._settings['lens_motor']['position']['static'][1],
                'p3': self._settings['lens_motor']['position']['static'][2]
            })
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
        print('started_updown_process: Updown movement started.')
        self.updown_slider.setStyleSheet('background: rgb(204, 0, 14);')
        self.updown_slider.sliderReleased.disconnect()
        self.updown_slider.sliderPressed.connect(lambda: self.servomotor_thread.stop_updown())

    @pyqtSlot(int)
    def ongoing_updown(self, position):
        print(f'Updown -> Current Position: {position}')
        self._settings['updown_motor']['position'] = position

    @pyqtSlot(int)
    def finished_updown(self, position):
        self._settings['updown_motor']['position'] = position
        print(f'Saving last position(updown): {position}')
        self.updown_slider.sliderPressed.connect(lambda: self.servomotor_thread.stop_updown())
        self.updown_slider.sliderPressed.disconnect()
        self.updown_slider.sliderReleased.connect(
            lambda: self.servomotor_thread.start_updown({
                'motor': self.updown_motor,
                'new_position': self.updown_slider.value(),
                'current_position': self._settings['updown_motor']['position'],
                'max_position': self._settings['updown_motor']['max_position'],
                'min_position': self._settings['updown_motor']['min_position']
            })
        )
        self.updown_slider.setStyleSheet('background: #565e7c;')
        self.updown_slider.setValue(position)

    @pyqtSlot()
    def started_autofocus(self):
        # print('started_updown_process: Updown movement started.')
        self.updown_slider.sliderReleased.disconnect()
        self.updown_slider.sliderPressed.connect(lambda: self.updown_worker.stop_command())

    @pyqtSlot(int)
    def ongoing_autofocus(self, position):
        print(f'Updown -> Current Position: {position}')
        self._settings['updown_motor']['position'] = position
        self.autofocus_thread.update_focus(self._focus)
        self.updown_slider.setDisabled(True)

    @pyqtSlot(int)
    def finished_autofocus(self, position):
        self._settings['updown_motor']['position'] = position
        self.updown_slider.setDisabled(False)
        print(f'Saving last position(updown): {position}')

    @pyqtSlot(object)
    def change_settings(self, settings):
        self._settings = settings
        self._save_settings()
        self._init_settings()


class AutofocusThread(QThread):
    started = pyqtSignal()
    ongoing = pyqtSignal(int)
    finished = pyqtSignal(int)

    def __init__(self):
        QtCore.QThread.__init__(self)
        self.commands_queue = queue.Queue(1)
        self.current_position = 0
        self.focus = 0
        self.threshold = 0
        self.max_position = 0
        self.min_position = 0

        self.moving = True
        self.running = True

        self.topped = False
        self.bottomed = False
        self.cycle = False

        self.focus_prev = 0
        self.focus_diff = 0

        self.direction = ''

    def __del__(self):
        self.wait()
        print("Closing Lens Thread.")

    def add_command(self, cmd):
        print('Adding command')
        self.commands_queue.put(cmd)
        self.moving = True

    def stop_command(self):
        self.moving = False

    def update_focus(self, focus):
        self.focus = focus

    def run(self):
        print('Auto focusing')
        while True:
            print('Autofocus waiting for command...')
            (self.current_position, self.focus, self.threshold, self.max_position, self.min_position) = self.commands_queue.get()

            self.focus_prev = self.focus
            self.topped = False
            self.bottomed = False

            while self.focus < self.threshold:
                sleep(0.01)
                self.ongoing.emit(self.current_position)
                self.focus_diff = self.focus_prev - self.focus
                print(f'Current Focus: {self.focus} - Previous Focus: {self.focus_prev}')
                print(f'Focus Difference: {self.focus_diff}')
                if self.focus_diff > 10:
                    self.direction = 'up'
                elif self.focus_diff < -10:
                    self.direction = 'down'

                # Go down first then up until image is not blurred
                if not self.topped and self.moving and self.current_position < self.max_position:  # Direction: Up
                    self.current_position += 10

                    if check_dependency('GPIO') is not None:
                        self.updown_motor.steps_rotate('ccw', 10)
                        self.ongoing.emit(self.current_position)
                    else:
                        sleep(0.5)
                        self.ongoing.emit(self.current_position)
                        print('Up')

                    if self.current_position >= self.max_position:
                        self.topped = True
                elif not self.bottomed and self.moving and self.current_position > self.min_position:  # Direction: Down
                    self.current_position -= 10

                    if check_dependency('GPIO') is not None:
                        self.updown_motor.steps_rotate('cw', 10)
                        self.ongoing.emit(self.current_position)
                    else:
                        sleep(0.5)
                        self.ongoing.emit(self.current_position)
                        print('Down')

                    if self.current_position <= self.min_position:
                        self.bottomed = True


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


class ServoMotorThread(QThread):
    move_leftright = pyqtSignal(int)
    move_forwardbackward = pyqtSignal(int)
    move_brightness = pyqtSignal(int)
    started_updown = QtCore.pyqtSignal()
    ongoing_updown = QtCore.pyqtSignal(int)
    finished_updown = QtCore.pyqtSignal(int)
    started_lens = pyqtSignal()
    ongoing_lens = pyqtSignal(int, int)
    finished_lens = pyqtSignal(int, int)

    def __init__(self):
        QtCore.QThread.__init__(self)
        self.commands_queue = queue.Queue(1)
        self.running_main = True
        self.running_updown = False
        self.running_lens = False
        self.running_lrfb = False

        self.updown_motor = {
            'motor': object, 'new_position': 0, 'current_position': 0,
            'max_position': 0, 'min_position': 0,
        }
        self.lens_motor = {
            'motor': object, 'lens_index': 0, 'current_position': 0,
            'p1': 0, 'p2': 0, 'p3': 0
        }
        self.lrfb_servo = {
            'widget': '', 'command': '', 'servo': object, 'current_position': 0, 'step':0
        }

    def __del__(self):
        self.wait()
        print("Closing Servo Motor Thread.")

    def start_updown(self, items):
        for key in self.updown_motor:
            self.updown_motor[key] = items[key]
        self.commands_queue.put(True)
        self.running_updown = True

    def stop_updown(self):
        self.running_updown = False

    def start_lens(self, items):
        for key in self.lens_motor:
            self.lens_motor[key] = items[key]
        self.commands_queue.put(True)
        self.running_lens = True

    def stop_lens(self):
        self.running_lens = False

    def start_lrfb(self, items):
        for key in self.lrfb_servo:
            self.lrfb_servo[key] = items[key]
        self.commands_queue.put(True)
        self.running_lrfb = True

    def stop_lrfb(self):
        self.running_lrfb = False

    def run(self):
        while self.running_main:
            queue_command = self.commands_queue.get()
            print('Waiting for command...')
            if self.running_updown:
                self.started_updown.emit()
                print(f'UpdownWorker -> process_command: Setting New Position: {self.updown_motor["new_position"]}')
                if self.updown_motor['new_position'] >= self.updown_motor['current_position']:
                    direction = "up"
                    steps = self.updown_motor['new_position'] - self.updown_motor['current_position']
                elif self.updown_motor['new_position'] <= self.updown_motor['current_position']:
                    direction = "down"
                    steps = self.updown_motor['current_position'] - self.updown_motor['new_position']

                for step in range(steps):
                    if self.running_updown and direction == "up" and self.updown_motor['current_position'] < \
                            self.updown_motor['max_position']:
                        self.updown_motor['current_position'] += 1
                        if check_dependency('GPIO') is not None:
                            self.updown_motor['motor'].rotate('ccw')
                        else:
                            sleep(1)
                        self.ongoing_updown.emit(self.updown_motor['current_position'])
                    elif self.running_updown and direction == "down" and self.updown_motor['current_position'] > \
                            self.updown_motor['min_position']:
                        self.updown_motor['current_position'] -= 1
                        if check_dependency('GPIO') is not None:
                            self.updown_motor['motor'].rotate('cw')
                        else:
                            sleep(1)
                        self.ongoing_updown.emit(self.updown_motor['current_position'])
                    else:
                        if self.updown_motor['current_position'] == self.updown_motor['max_position']:
                            print("UpdownWoker -> process_command: Upper Limit Reached.")
                        elif self.updown_motor['current_position'] == self.updown_motor['min_position']:
                            print("UpdownWoker -> process_command: Lower Limit Reached.")
                        else:
                            print("UpdownWoker -> process_command: Process Canceled.")
                        self.finished_updown.emit(self.updown_motor['current_position'])
                        break
                self.finished_updown.emit(self.updown_motor['current_position'])
            elif self.running_lens:
                self.started_lens.emit()
                # 'motor': object, 'lens_index': 0, 'current_position': 0,
                # 'p1': 0, 'p2': 0, 'p3': 0
                motor = self.lens_motor['motor']
                lens_index = self.lens_motor['lens_index']
                current_position = self.lens_motor['current_position']
                p1 = self.lens_motor['p1']
                p2 = self.lens_motor['p2']
                p3 = self.lens_motor['p3']
                if lens_index == 0:
                    # Rotate Stepper To next lens
                    print('Changing Lens: 0->1')
                    while self.running_lens and current_position < p2:  # 2000
                        current_position += 1
                        if check_dependency('GPIO') is not None:
                            motor.step_rotate('cw')
                        else:
                            sleep(0.5)
                        self.ongoing_lens.emit(lens_index, current_position)

                    if self.running_lens:
                        lens_index = 1
                        self.running_lens = False
                        print('Cycle complete')
                    else:
                        print('Cycle incomplete.')
                        print(f'Current Position: {current_position} - Expected Position: {p2}')

                elif lens_index == 1:
                    # Rotate Stepper clockwise going to lens 2
                    print('Changing Lens: 1->2')
                    while self.running_lens and current_position < p3:  # 4000
                        current_position += 1
                        if check_dependency('GPIO') is not None:
                            motor.step_rotate('cw')
                        else:
                            sleep(0.5)
                        self.ongoing_lens.emit(lens_index, current_position)

                    if self.running_lens:
                        lens_index = 2
                        self.running_lens = False
                        print('Cycle complete')
                    else:
                        print('Cycle incomplete.')
                        print(f'Current Position: {current_position} - Expected Position: {p3}')

                elif lens_index == 2:
                    # Rotate Stepper counter clockwise returning to lens 3
                    print('Changing Lens: 2->0')
                    while self.running_lens and current_position > p1:  # 0
                        current_position -= 1
                        if check_dependency('GPIO') is not None:
                            motor.step_rotate('ccw')
                        else:
                            sleep(0.5)
                        self.ongoing_lens.emit(lens_index, current_position)

                    if self.running_lens:
                        lens_index = 0
                        self.running_lens = False
                        print('Cycle complete')
                    else:
                        print('Cycle incomplete.')
                        print(f'Current Position: {current_position} - Expected Position: {p1}')
                self.finished_lens.emit(lens_index, current_position)
            elif self.running_lrfb:
                widget = self.lrfb_servo['widget']
                command = self.lrfb_servo['command']
                current_position = self.lrfb_servo['current_position']
                servo = self.lrfb_servo['servo']
                step = self.lrfb_servo['step']

                if widget == 'button':
                    if command == 'left':
                        current_position += step
                        if check_dependency('GPIO') is not None:
                            servo.set_angle(current_position)
                        self.move_leftright.emit(current_position)
                    elif command == 'right':
                        current_position -= step
                        if check_dependency('GPIO') is not None:
                            servo.set_angle(current_position)
                        self.move_leftright.emit(current_position)
                    elif command == 'forward':
                        current_position += step
                        if check_dependency('GPIO') is not None:
                            servo.set_angle(current_position)
                        self.move_forwardbackward.emit(current_position)
                    elif command == 'backward':
                        current_position -= step
                        if check_dependency('GPIO') is not None:
                            servo.set_angle(current_position)
                        self.move_forwardbackward.emit(current_position)
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
                    self.move_leftright.emit(current_position)
                elif command == 'right':
                    current_position -= step
                    if check_dependency('GPIO') is not None:
                        servo.set_angle(current_position)
                    self.move_leftright.emit(current_position)
                elif command == 'forward':
                    current_position += step
                    if check_dependency('GPIO') is not None:
                        servo.set_angle(current_position)
                    self.move_forwardbackward.emit(current_position)
                elif command == 'backward':
                    current_position -= step
                    if check_dependency('GPIO') is not None:
                        servo.set_angle(current_position)
                    self.move_forwardbackward.emit(current_position)
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
    saved_settings = pyqtSignal(object)

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self._application_settings = QSettings()
        self._settings = self._application_settings.value('automi_settings')
        print(self._settings)

    def save_settings(self):
        print('Changing Settings...')
        settings_list = {
            'camera': {'index': 'int', 'blur.threshold': 'int',
                       'names.image': 'str', 'names.video': 'str'
                       },
            # 'brightness_servo': {'max_position': 'int', 'min_position': 'int',
            #                      'pin': 'int', 'position': 'int', 'ticks': 'int',
            #                      },
            # 'directories': {'icons': 'str', 'images': 'str', 'videos': 'str', },
            # 'forward-backward_servo': {'pin': 'int', 'position': 'int', 'steps': 'int', },
            # 'left-right_servo': {'pin': 'int', 'position': 'int', 'steps': 'int', },
            # 'lens_motor': {'index': 'int', 'pins.delay': 'float', 'pins.dir': 'int',
            #                'pins.mode_pins.0': 'int', 'pins.mode_pins.1': 'int', 'pins.mode_pins.2': 'int',
            #                'resolution': 'int', 'step': 'int', 'step_angle': 'int',
            #                'position.dynamic': 'int', 'position.static.0': 'int', 'position.static.1': 'int',
            #                'position.static.2': 'int',
            #                },
            # 'updown_motor': {'max_position': 'int', 'min_position': 'int',
            #                  'pins.delay': 'float', 'pins.dir': 'int',
            #                  'pins.mode_pins.0': 'int', 'pins.mode_pins.1': 'int', 'pins.mode_pins.2': 'int',
            #                  'resolution': 'int', 'step': 'int', 'step_angle': 'int',
            #                  'position': 'int',
            #                  },
            # 'server': {'video_port': 'int', },
            # 'zoom_slider': {'max_position': 'int', 'min_position': 'int', 'position': 'int'},
        }
        settings_widget = {
            'camera': (self.camera_index, self.blur_threshold, self.name_image, self.name_video),
        }

        index = 0
        for setting, items in settings_list.items():
            print(f'{setting}: {items}')
            for item, type in items.items():
                results = item.split('.')
                len_results = len(results)
                if len_results == 1:
                    results[0] = convert(results[0])
                    self._settings[setting][results[0]] = convert(settings_widget[setting][index].text())
                elif len_results == 2:
                    results[0] = convert(results[0])
                    results[1] = convert(results[1])
                    self._settings[setting][results[0]][results[1]] = convert(settings_widget[setting][index].text())
                elif len_results == 3:
                    results[0] = convert(results[0])
                    results[1] = convert(results[1])
                    results[2] = convert(results[2])
                    self._settings[setting][results[0]][results[1]][results[2]] = convert(settings_widget[setting][index].text())
                # if type == 'str':
                #     if len_results == 1:
                #         self._settings[setting][results[0]] = settings_widget[setting][index].text()
                #     elif len_results == 2:
                #         self._settings[setting][results[0]][results[1]] = settings_widget[setting][index].text()
                #     elif len_results == 3:
                #         results[2] = convert(results[2])
                #         self._settings[setting][results[0]][results[1]][results[2]] = settings_widget[setting][index].text()
                # elif type == 'float':
                #     if len_results == 1:
                #         self._settings[setting][results[0]] = float(settings_widget[setting][index].text())
                #     elif len_results == 2:
                #         self._settings[setting][results[0]][results[1]] = float(settings_widget[setting][index].text())
                #     elif len_results == 3:
                #         results[2] = convert(results[2])
                #         self._settings[setting][results[0]][results[1]][results[2]] = float(settings_widget[setting][
                #             index].text())
                # else:
                #     if len_results == 1:
                #         self._settings[setting][results[0]] = int(settings_widget[setting][index].text())
                #     elif len_results == 2:
                #         self._settings[setting][results[0]][results[1]] = int(settings_widget[setting][index].text())
                #     elif len_results == 3:
                #         results[2] = convert(results[2])
                #         self._settings[setting][results[0]][results[1]][results[2]] = int(settings_widget[setting][index].text())
                index += 1

        # self._settings['camera']['names']['image'] = self.name_image.text()
        # self._settings['camera']['names']['video'] = self.name_video.text()
        # self._settings['camera']['index'] = int(self.camera_index.text())
        # self._settings['camera']['blur']['threshold'] = int(self.blur_threshold.text())
        print(self._settings)
        self.saved_settings.emit(self._settings)


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
