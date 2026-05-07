# main.py
import gc
import json
import time

import machine
import micropython
from services.mqtt import MqttManager
from services.wifi import WiFiManager

import config


class CoffeeController:
    BUTTON_DEBOUNCE_MS = 200

    def __init__(self):
        # Hardware initialization
        self.led = machine.Pin(config.LED_PIN, machine.Pin.OUT)
        self.btn = machine.Pin(config.BTN_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
        self.cmd = machine.Pin(config.CMD_PIN, machine.Pin.OUT)
        self.status = machine.Pin(config.STATUS_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

        # Service initialization
        self.wifi = WiFiManager(config.WIFI_SSID, config.WIFI_PASSWORD)
        self.mqtt = MqttManager(
            config.COFFEE_MAKER_ID, config.MQTT_HOST, config.MQTT_PORT, config.MQTT_USERNAME, config.MQTT_PASSWORD
        )

        self.wdt = machine.WDT(timeout=10000)

        # State variables (replacing global variables)
        self.last_btn_press_time: int = 0
        self.current_status: int = 0

    def send_coffee_maker_cmd(self, _):
        print(f"Update coffee maker status to '{not self.current_status}'.")
        self.cmd.value(1)
        time.sleep(0.2)
        self.cmd.value(0)
        time.sleep(0.3)
        self.update_coffee_maker_status(not self.status.value())

    def handle_button(self, pin: machine.Pin):
        current_ticks = time.ticks_ms()
        duration = time.ticks_diff(current_ticks, self.last_btn_press_time)

        if duration >= self.BUTTON_DEBOUNCE_MS:
            self.last_btn_press_time = current_ticks
            micropython.schedule(self.send_coffee_maker_cmd, None)

    def update_coffee_maker_status(self, status: bool):
        if status == self.current_status:
            return
        self.current_status = status

        self.led.value(status)
        print(f"Coffee maker status updated to '{status}'.")

    def handle_status(self, pin: machine.Pin):
        micropython.schedule(self.update_coffee_maker_status, not pin.value())

    def handle_coffee_command(self, topic: bytes, msg: bytes):
        try:
            if len(msg) > 512:
                return

            # Security: MicroPython umqtt returns bytes, they need to be decoded
            payload: dict = json.loads(msg.decode("utf-8"))
            # print(f"LED command received: '{payload}'.")

            if isinstance(payload, dict) and "status" in payload:
                new_val = 1 if payload["status"] in (1, True, "1") else 0
                self.led.value(new_val)
                self.publish_led_status()
        except Exception as e:
            print(f"Error handling command: {e}")

    def ensure_connections(self) -> bool:
        """Checks connection status and attempts to restore it if necessary."""
        if not self.wifi.is_connected():
            print("WiFi lost. Attempting to reconnect...")
            if not self.wifi.connect(retries=2):
                print("Unable to connect to WiFi at startup, restart...")
                time.sleep(5)
                machine.reset()

            # If WiFi reconnected, the MQTT client must be restarted
            self.mqtt.disconnect()
            if not self.mqtt.connect():
                print("Unable to connect to MQTT at startup, restart...")
                time.sleep(5)
                machine.reset()

            # Resubscribe after reconnection
            self.mqtt.subscribe(config.COFFEE_MAKER_COMMAND_TOPIC, self.handle_coffee_command)

        current_ticks = time.time()
        if current_ticks - self.last_ping > 30:
            try:
                self.mqtt.ping()
                self.last_ping = current_ticks
            except Exception:
                print("Unable to ping MQTT server, restart...")
                time.sleep(5)
                machine.reset()

        return True

    def run(self):
        print("Starting ESP32...")

        self.cmd.value(0)
        self.led.value(not self.status.value())

        self.btn.irq(trigger=machine.Pin.IRQ_FALLING, handler=self.handle_button)
        self.status.irq(trigger=machine.Pin.IRQ_FALLING | machine.Pin.IRQ_RISING, handler=self.handle_status)

        print("ESP32 ready.")

        # Main loop
        while True:
            try:
                gc.collect()  # Libère la RAM inutilisée à chaque cycle
                self.wdt.feed()

                time.sleep(1)
            except Exception as e:
                # Catch other unexpected errors to prevent a total crash
                print(f"Unexpected error: {e}, restart...")
                time.sleep(2)
                machine.reset()
