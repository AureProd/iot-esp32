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
        self.ready_btn = ButtonController(config.READY_BTN_PIN, self.toggle_coffee_maker_ready_status)
        self.run_cmd = machine.Pin(config.RUN_CMD_PIN, machine.Pin.OUT)
        self.run_status = ButtonController(config.RUN_STATUS_PIN, self.toggle_coffee_maker_run_status)

        # Service initialization
        self.wifi = WiFiManager(config.WIFI_SSID, config.WIFI_PASSWORD)
        self.mqtt = MqttManager(
            config.COFFEE_MAKER_ID, config.MQTT_HOST, config.MQTT_PORT, config.MQTT_USERNAME, config.MQTT_PASSWORD
        )

        self.wdt = machine.WDT(timeout=10_000)

        # State variables (replacing global variables)
        self.last_publish_status_time = time.ticks_ms()
        self.current_run_status = False
        self.current_ready_status = False

    def start_coffee_maker(self):
        if not self.current_ready_status:
            print("ERROR: Coffee-maker not ready to start")
            raise RuntimeError("Coffee-maker not ready to start")

        if self.current_run_status:
            print("ERROR: Coffee-maker already started")
            raise RuntimeError("Coffee-maker already started")

        print("Start coffee maker")
        self.run_cmd.value(1)
        time.sleep(0.2)
        self.run_cmd.value(0)
        # time.sleep(0.3)
        # self.update_coffee_maker_run_status(not self.run_status.value())

    def stop_coffee_maker(self):
        if not self.current_run_status:
            print("ERROR: Coffee-maker not started")
            raise RuntimeError("Coffee-maker not started")

        print("Stop coffee maker")
        self.run_cmd.value(1)
        time.sleep(0.2)
        self.run_cmd.value(0)
        # time.sleep(0.3)
        # self.update_coffee_maker_run_status(not self.run_status.value())

    def toggle_coffee_maker_run_status(self):
        try:
            self.update_coffee_maker_run_status(not self.run_status.value())
        except OSError:
            print("Offline: state changed locally but could not publish to MQTT.")

    def toggle_coffee_maker_ready_status(self):
        try:
            self.update_coffee_maker_ready_status(not self.ready_led.value())
        except OSError:
            print("Offline: state changed locally but could not publish to MQTT.")

    def update_coffee_maker_run_status(self, status: bool):
        if status == self.current_run_status:
            return

        self.current_run_status = status
        print(f"Save coffee maker run status: '{status}'")
        self.mqtt.publish(config.COFFEE_MAKER_RUN_STATUS_TOPIC, {"status": status, "id": config.COFFEE_MAKER_ID})

        if not status:
            print("Reset coffee maker ready status when coffee maker stopped")
            self.update_coffee_maker_ready_status(False)

    def update_coffee_maker_ready_status(self, status: bool):
        if status == self.current_ready_status:
            return

        self.current_ready_status = status
        self.ready_led.value(status)
        print(f"Save coffee maker ready status: '{status}'")
        self.mqtt.publish(
            config.COFFEE_MAKER_READY_STATUS_TOPIC, {"status": status, "id": config.COFFEE_MAKER_ID}, retain=True
        )

    def refresh_coffee_maker_status(self):
        self.mqtt.publish(
            config.COFFEE_MAKER_RUN_STATUS_TOPIC, {"status": not self.run_status.value(), "id": config.COFFEE_MAKER_ID}
        )
        self.mqtt.publish(
            config.COFFEE_MAKER_READY_STATUS_TOPIC,
            {"status": self.current_ready_status, "id": config.COFFEE_MAKER_ID},
            retain=True,
        )

    def on_mqtt_message_received(self, encoded_topic: bytes, msg: bytes):
        """
        Simplified message processing.
        Expects JSON like: {"status": 1} or {"status": True}
        """
        if len(msg) > 512:
            return  # RAM Protection

        try:
            topic = encoded_topic.decode()
            payload: dict = json.loads(msg)

            if "status" in payload:
                status = payload["status"] in (1, True, "1")

                if topic == config.COFFEE_MAKER_COMMAND_TOPIC:
                    if status:
                        self.start_coffee_maker()
                    else:
                        self.stop_coffee_maker()

                elif topic == config.COFFEE_MAKER_READY_STATUS_TOPIC:
                    print(f"Read last coffee maker stored ready status: {status}")
                    self.update_coffee_maker_ready_status(status)
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
