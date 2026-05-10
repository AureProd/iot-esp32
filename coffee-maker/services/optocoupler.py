import time

import machine
import micropython


class OptocouplerController:
    # Un tout petit debounce (50ms) au cas où le signal de la machine de café
    # n'est pas parfaitement net lors de l'allumage/extinction
    DEBOUNCE_MS = 50

    def __init__(self, pin_num: int, on_change_callback):
        # L'optocoupleur a généralement besoin d'un PULL_UP s'il est monté en "open-collector"
        self._pin = machine.Pin(pin_num, machine.Pin.IN, machine.Pin.PULL_UP)

        self._on_change_callback = on_change_callback
        self._last_state = self._pin.value()
        self._last_trigger_time = 0
        self._is_task_scheduled = False
        self._execute_cb_ref = self._execute_callback

        # Interruption déclenchée sur n'importe quel changement (allumage OU extinction)
        self._pin.irq(trigger=machine.Pin.IRQ_FALLING | machine.Pin.IRQ_RISING, handler=self._handle_interrupt)

    def _execute_callback(self, _):
        self._is_task_scheduled = False
        self._on_change_callback()

    def _handle_interrupt(self, pin: machine.Pin):
        current_ticks = time.ticks_ms()
        current_state = pin.value()

        # Si l'état a changé ET que le délai anti-rebond est respecté
        if (
            current_state != self._last_state
            and time.ticks_diff(current_ticks, self._last_trigger_time) > self.DEBOUNCE_MS
        ):
            self._last_state = current_state
            self._last_trigger_time = current_ticks

            if not self._is_task_scheduled:
                try:
                    self._is_task_scheduled = True
                    micropython.schedule(self._execute_cb_ref, None)
                except RuntimeError:
                    self._is_task_scheduled = False

    def value(self) -> bool:
        # Retourne True si le pin est à 1, False s'il est à 0.
        return self._pin.value() == 1
