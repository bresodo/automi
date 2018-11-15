def _change_lens(self):
    lens_index = self._settings['lens']['index']
    current_position = self._settings['lens']['position']['dynamic']
    if lens_index == 0:
        # Rotate Stepper To next lens
        print('Changing Lens: 0->1')
        lens_index = 1
        while current_position < self._settings['lens']['position']['static'][0]:
            self._commands_queue.put(['button', 'cl', 'cw'])
            current_position += 1
            self._settings['lens']['position']['dynamic'] = current_position

    elif lens_index == 1:
        # Rotate Stepper clockwise going to lens 2
        print('Changing Lens: 1->2')
        lens_index = 2
        while current_position < self._settings['lens']['position']['static'][1]:
            self._commands_queue.put(['button', 'cl', 'cw'])
            self._settings['lens']['position']['dynamic'] = current_position

    elif lens_index == 2:
        # Rotate Stepper counter clockwise returning to lens 0
        print('Changing Lens: 2->0')
        lens_index = 0
        while current_position < self._settings['lens']['position']['static'][2]:
            self._commands_queue.put(['button', 'cl', 'ccw'])
            self._settings['lens']['position']['dynamic'] = current_position

    self._settings['lens']['index'] = lens_index