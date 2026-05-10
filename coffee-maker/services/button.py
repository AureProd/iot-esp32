import time

import machine
import micropython


class ButtonController:
    DEBOUNCE_MS = 100
    MIN_PRESS_DURATION_MS = 80

    def __init__(self, button_pin: int, on_press_callback):
        self._btn = machine.Pin(button_pin, machine.Pin.IN, machine.Pin.PULL_UP)

        # On utilise None pour différencier l'absence d'appui d'un temps à "0"
        self._press_time = None
        self._last_trigger_time = 0
        self._is_task_scheduled = False
        self._on_press_callback = on_press_callback

        # Pré-allocation de la référence pour éviter les MemoryError dans l'interruption
        self._execute_cb_ref = self._execute_callback

        # Configure hardware interrupt for both falling and rising edges
        self._btn.irq(trigger=machine.Pin.IRQ_FALLING | machine.Pin.IRQ_RISING, handler=self._handle_interrupt)

    def _execute_callback(self, _):
        # Reset the scheduling flag and execute the user-defined callback
        self._is_task_scheduled = False
        self._on_press_callback()

    def _handle_interrupt(self, pin: machine.Pin):
        current_ticks = time.ticks_ms()

        # Button pressed (active low due to PULL_UP resistor)
        if pin.value() == 0:
            self._press_time = current_ticks

        # Button released - EXÉCUTE SEULEMENT SI UN APPUI A COMMENCÉ
        elif self._press_time is not None:
            press_duration = time.ticks_diff(current_ticks, self._press_time)

            # Validate minimum press duration to filter out noise
            if press_duration >= self.MIN_PRESS_DURATION_MS:
                # Apply debounce logic
                if time.ticks_diff(current_ticks, self._last_trigger_time) > self.DEBOUNCE_MS:
                    if not self._is_task_scheduled:
                        try:
                            self._is_task_scheduled = True
                            self._last_trigger_time = current_ticks
                            # Utilisation de la méthode pré-allouée
                            micropython.schedule(self._execute_cb_ref, None)
                        except RuntimeError:
                            # Fallback if schedule queue is full
                            self._is_task_scheduled = False

            # Reset press tracking
            self._press_time = None

    def value(self) -> bool:
        return self._btn.value() == 1
