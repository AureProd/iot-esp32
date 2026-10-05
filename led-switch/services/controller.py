# controller.py
import gc
import json
import time

import machine
from services.button import ButtonController
from services.mqtt import MqttManager
from services.wifi import WiFiManager

import config


class LEDController:
    PUBLISH_STATUS_INTERVAL_MS = 180_000  # 3 minutes
    PING_INTERVAL_MS = 15_000  # A dead MQTT connection is detected within ~1 minute

    def __init__(self):
        # Hardware initialization
        self.led = machine.Pin(config.LED_PIN, machine.Pin.OUT)
        self.button = ButtonController(config.BTN_PIN, self.toggle_led)

        # Service initialization
        self.wifi = WiFiManager(config.WIFI_SSID, config.WIFI_PASSWORD)
        self.mqtt = MqttManager(
            config.LED_ID, config.MQTT_HOST, config.MQTT_PORT, config.MQTT_USERNAME, config.MQTT_PASSWORD
        )

        # Hardware Watchdog Timer (30 seconds timeout, leaves room for slow WiFi/TLS connections)
        self.wdt = machine.WDT(timeout=30_000)
        self.last_publish_status_time = time.ticks_ms()
        self.last_ping_time = time.ticks_ms()

    def on_mqtt_message_received(self, topic: bytes, msg: bytes):
        """
        Simplified message processing.
        Expects JSON like: {"status": 1} or {"status": True}
        """
        if len(msg) > 512:
            return  # RAM Protection

        try:
            payload = json.loads(msg)
            if "status" in payload:
                # Set LED state: 1/True/"1" turns it ON, anything else turns it OFF
                new_state = 1 if payload["status"] in (1, True, "1") else 0
                print(f"Command received: status={new_state}")
                self.led.value(new_state)
                self.publish_led_status()
        except (ValueError, KeyError):
            print("Received invalid message format, ignoring.")

    def publish_led_status(self):
        """Publishes current state. If network is down, an OSError will be raised."""
        self.mqtt.publish(config.LED_STATUS_TOPIC, {"status": self.led.value(), "id": config.LED_ID})

    def toggle_led(self):
        """Triggered by physical button interrupt."""
        self.led.value(not self.led.value())
        try:
            self.publish_led_status()
        except OSError:
            print("Offline: state changed locally but could not publish to MQTT.")

    def connect_network(self):
        """
        Full connection sequence.
        Raises OSError if any step fails, triggering the reconnection logic.
        """
        print("Establishing network connections...")

        self.wdt.feed()
        gc.collect()

        # WiFiManager.connect() raises OSError if it fails
        if not self.wifi.is_connected():
            self.wifi.connect(feed=self.wdt.feed)

        # Reset MQTT state and reconnect
        self.mqtt.disconnect()
        self.wdt.feed()
        self.mqtt.connect()
        self.wdt.feed()
        self.mqtt.set_callback(self.on_mqtt_message_received)

        self.mqtt.subscribe(config.LED_COMMAND_TOPIC)
        self.publish_led_status()
        self.last_ping_time = time.ticks_ms()
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

                    if not self.wifi.is_connected():
                        raise OSError("WiFi connection lost")

                    # check_for_messages() will raise OSError if the connection is lost
                    self.mqtt.check_for_messages()

                    # Keep-alive: raises OSError if the broker stopped answering
                    if time.ticks_diff(time.ticks_ms(), self.last_ping_time) >= self.PING_INTERVAL_MS:
                        self.mqtt.ping()
                        self.last_ping_time = time.ticks_ms()

                    # Periodic status update
                    if (
                        time.ticks_diff(time.ticks_ms(), self.last_publish_status_time)
                        >= self.PUBLISH_STATUS_INTERVAL_MS
                    ):
                        self.publish_led_status()
                        self.last_publish_status_time = time.ticks_ms()
                        gc.collect()  # Safe periodic memory cleanup

                    time.sleep(0.1)

            except OSError as e:
                # Catch-all for network issues (WiFi lost, MQTT timeout, etc.)
                print(f"Network error detected: {e}. Retrying in 5 seconds...")
                # The WiFi may look connected while the access point already dropped us:
                # force a fresh association on the next attempt
                self.mqtt.disconnect()
                self.wifi.disconnect()
                for _ in range(10):
                    self.wdt.feed()
                    time.sleep(0.5)
                # The external loop restarts and calls connect_network() again

            except Exception as e:
                # Catch-all for fatal software errors
                print(f"Critical error: {e}. Resetting device...")
                time.sleep(2)
                machine.reset()
