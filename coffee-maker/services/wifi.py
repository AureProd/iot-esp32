import time

import network


class WiFiManager:
    def __init__(self, ssid: str, password: str):
        self.ssid = ssid
        self.password = password
        self._wlan = network.WLAN(network.STA_IF)

    def connect(self, timeout_ms: int = 10_000, retries: int = 3):
        """
        Attempts to connect to the WiFi network.
        Raises an OSError if the connection fails after all retries.
        """
        self._wlan.active(True)

        for attempt in range(retries):
            if not self._wlan.isconnected():
                print(f"WiFi connection attempt {attempt + 1}/{retries}...")
                self._wlan.connect(self.ssid, self.password)

                start_time = time.ticks_ms()
                # Wait for connection or timeout
                while not self._wlan.isconnected() and time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
                    time.sleep(0.5)

            if self._wlan.isconnected():
                print("WiFi connected successfully.")
                print("IP Address:", self._wlan.ifconfig()[0])
                return  # Success, exit the function

            print("WiFi connection attempt failed.")
            time.sleep(2)

        # If the loop finishes without returning, all retries failed
        raise OSError("Failed to connect to WiFi network.")

    def is_connected(self) -> bool:
        """Returns True if currently connected to the WiFi network."""
        return self._wlan.isconnected()

    def disconnect(self):
        """Disconnects from the WiFi network if connected."""
        if self._wlan.isconnected():
            self._wlan.disconnect()
