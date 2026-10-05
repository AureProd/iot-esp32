import time

import network


class WiFiManager:
    def __init__(self, ssid: str, password: str):
        self.ssid = ssid
        self.password = password
        self._wlan = network.WLAN(network.STA_IF)
        self._configure()

    def _configure(self):
        self._wlan.active(True)
        # Disable WiFi power saving (causes heavy packet loss/timeouts with a weak signal)
        # and use full transmit power
        self._wlan.config(pm=self._wlan.PM_NONE, txpower=20)

    def _sleep(self, duration_ms: int, feed=None):
        """Sleeps in small steps, feeding the watchdog if a feed callback is given."""
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < duration_ms:
            if feed:
                feed()
            time.sleep(0.5)

    def _reset_interface(self):
        """Stops any pending connection attempt so connect() can be called again."""
        try:
            self._wlan.disconnect()
        except OSError:
            pass
        if self._wlan.status() == network.STAT_CONNECTING:
            # Station is still stuck in "connecting" state: restart the interface
            self._wlan.active(False)
            time.sleep(0.5)
            self._configure()

    def connect(self, timeout_ms: int = 10_000, retries: int = 3, feed=None):
        """
        Attempts to connect to the WiFi network.
        Raises an OSError if the connection fails after all retries.
        `feed` is an optional callback (e.g. watchdog feed) called while waiting.
        """
        self._wlan.active(True)

        for attempt in range(retries):
            if not self._wlan.isconnected():
                print(f"WiFi connection attempt {attempt + 1}/{retries}...")
                self._reset_interface()
                try:
                    self._wlan.connect(self.ssid, self.password)
                except OSError as e:
                    print(f"WiFi connect call failed: {e}")
                else:
                    start_time = time.ticks_ms()
                    # Wait for connection or timeout
                    while not self._wlan.isconnected() and time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
                        if feed:
                            feed()
                        time.sleep(0.5)

            if self._wlan.isconnected():
                print("WiFi connected successfully.")
                print("IP Address:", self._wlan.ifconfig()[0])
                return  # Success, exit the function

            print("WiFi connection attempt failed.")
            self._sleep(2_000, feed)

        # If the loop finishes without returning, all retries failed
        raise OSError("Failed to connect to WiFi network.")

    def is_connected(self) -> bool:
        """Returns True if currently connected to the WiFi network."""
        return self._wlan.isconnected()

    def disconnect(self):
        """Disconnects from the WiFi network if connected."""
        if self._wlan.isconnected():
            self._wlan.disconnect()
