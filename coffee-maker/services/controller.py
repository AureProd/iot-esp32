# main.py
import gc
import json
import time

import machine
from services.button import ButtonController
from services.mqtt import MqttManager
from services.wifi import WiFiManager

import config


class CoffeeController:
    PUBLISH_STATUS_INTERVAL_MS = 180_000  # 3 minutes

    def __init__(self):
        # Hardware initialization
        self.ready_led = machine.Pin(config.READY_LED_PIN, machine.Pin.OUT)
        self.ready_btn = ButtonController(config.READY_BTN_PIN, self.handle_ready_btn_click)
        self.run_cmd = machine.Pin(config.RUN_CMD_PIN, machine.Pin.OUT)
        self.run_led = ButtonController(config.RUN_STATUS_PIN, self.handle_run_status)

        # Service initialization
        self.wifi = WiFiManager(config.WIFI_SSID, config.WIFI_PASSWORD)
        self.mqtt = MqttManager(
            config.COFFEE_MAKER_ID, config.MQTT_HOST, config.MQTT_PORT, config.MQTT_USERNAME, config.MQTT_PASSWORD
        )

        self.wdt = machine.WDT(timeout=10_000)

        # State variables (replacing global variables)
        self.last_publish_status_time = time.ticks_ms()
        self.ready_status = False
        self.run_status = False

    def update_ready_status(self, status: bool):
        if status == self.ready_status:
            return

        self.ready_status = status
        print(f"Update coffee maker ready status: '{status}'")

    def publish_ready_status(self):
        print(f"Publish coffee maker ready status: '{self.ready_status}'")
        self.mqtt.publish(
            config.COFFEE_MAKER_READY_STATUS_TOPIC,
            {"status": self.ready_status, "id": config.COFFEE_MAKER_ID},
            retain=True,
        )

    def update_run_status(self, status: bool):
        if status == self.run_status:
            return

        self.run_status = status
        print(f"Update coffee maker run status: '{status}'")

    def publish_run_status(self):
        print(f"Publish coffee maker run status: '{self.run_status}'")
        self.mqtt.publish(
            config.COFFEE_MAKER_RUN_STATUS_TOPIC, {"status": self.run_status, "id": config.COFFEE_MAKER_ID}
        )

    def handle_ready_btn_click(self):
        if self.run_status:
            self.stop_coffee_maker()
        else:
            self.update_ready_status(not self.ready_status)

    def start_coffee_maker(self):
        if not self.ready_status:
            print("Coffee-maker not ready to start")
            return

        if self.run_status:
            print("Coffee-maker already started")
            return

        print("Start coffee maker")

        self.run_cmd.value(1)
        time.sleep(0.2)
        self.run_cmd.value(0)
        time.sleep(0.3)

        self.update_ready_status(False)
        self.update_run_status(not self.run_led.value())

        self.publish_ready_status()
        self.publish_run_status()

    def stop_coffee_maker(self):
        if not self.run_status:
            print("Coffee-maker not started")
            return

        print("Stop coffee maker")

        self.run_cmd.value(1)
        time.sleep(0.2)
        self.run_cmd.value(0)
        time.sleep(0.3)

        self.update_run_status(not self.run_led.value())

        self.publish_run_status()

    def handle_run_status(self):
        if run_status := not self.run_led.value():
            if self.ready_status:
                self.update_ready_status(False)

        self.update_run_status(run_status)

        self.publish_ready_status()
        self.publish_run_status()

    def refresh_coffee_maker_status(self):
        print(f"Refresh coffee maker status: run status: '{self.run_status}', ready status: '{self.ready_status}'")
        self.publish_ready_status()
        self.publish_run_status()

    def on_mqtt_message_received(self, encoded_topic: bytes, msg: bytes):
        """
        Simplified message processing.
        Expects JSON like: {"status": 1} or {"status": True}
        """
        if len(msg) > 512:
            return  # RAM Protection

        try:
            topic = encoded_topic.decode("utf-8")
            payload: dict = json.loads(msg.decode("utf-8"))

            if "status" in payload:
                status = payload["status"] in (1, True, "1")

                if topic == config.COFFEE_MAKER_COMMAND_TOPIC:
                    if status:
                        self.start_coffee_maker()
                    else:
                        self.stop_coffee_maker()

                elif topic == config.COFFEE_MAKER_READY_STATUS_TOPIC:
                    print(f"Read last coffee maker stored ready status: {status}")
                    self.update_ready_status(status)
                    self.mqtt.unsubscribe(config.COFFEE_MAKER_READY_STATUS_TOPIC)
        except (ValueError, KeyError):
            print("Received invalid message format, ignoring.")

    def connect_network(self):
        """
        Full connection sequence.
        Raises OSError if any step fails, triggering the reconnection logic.
        """
        print("Establishing network connections...")

        gc.collect()

        # WiFiManager.connect() now raises OSError if it fails
        if not self.wifi.is_connected():
            self.wifi.connect(retries=3)

        # Reset MQTT state and reconnect
        self.mqtt.disconnect()
        self.mqtt.connect()
        self.mqtt.set_callback(self.on_mqtt_message_received)

        self.mqtt.subscribe(config.COFFEE_MAKER_COMMAND_TOPIC)

        # Read last ready status of coffee maker
        self.mqtt.subscribe(config.COFFEE_MAKER_READY_STATUS_TOPIC)
        print("Check last coffee maker ready status...")
        self.mqtt.check_for_messages()

        self.update_run_status(not self.run_led.value())
        self.publish_run_status()

        print("System is online and ready.")

    def run(self):
        """Main execution loop with automatic recovery."""
        print("Starting ESP32 Application...")

        # EXTERNAL LOOP: Handles reconnections
        while True:
            try:
                # Try to connect. If this fails, it goes straight to 'except OSError'
                self.connect_network()

                # INTERNAL LOOP: Normal operation
                while True:
                    self.wdt.feed()

                    # check_for_messages() will raise OSError if the connection is lost
                    self.mqtt.check_for_messages()

                    # Periodic status update and keep-alive
                    if (
                        time.ticks_diff(time.ticks_ms(), self.last_publish_status_time)
                        >= self.PUBLISH_STATUS_INTERVAL_MS
                    ):
                        self.mqtt.ping()  # Verifies if broker is still reachable
                        self.refresh_coffee_maker_status()
                        self.last_publish_status_time = time.ticks_ms()
                        gc.collect()  # Safe periodic memory cleanup

                    time.sleep(0.1)

            except OSError as e:
                # Catch-all for network issues (WiFi lost, MQTT timeout, etc.)
                print(f"Network error detected: {e}. Retrying in 5 seconds...")
                time.sleep(5)
                # The external loop restarts and calls connect_network() again

            except Exception as e:
                # Catch-all for fatal software errors
                print(f"Critical error: {e}. Resetting device...")
                time.sleep(2)
                machine.reset()
