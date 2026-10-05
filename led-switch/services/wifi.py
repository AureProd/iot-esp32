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

    def _reset_interface(self):
        """Stops any pending connection attempt so connect() can be called again."""
        try:
            self._wlan.disconnect()
        except OSError:
            pass
        # Restart the interface: after a silent drop by the access point, the driver can stay
        # stuck in "connecting" state, while a fresh interface reconnects within a few seconds
        self._wlan.active(False)
        time.sleep(0.5)
        self._configure()

    def connect(self, timeout_ms: int = 15_000, feed=None):
        """
        Attempts to connect to the WiFi network.
        Raises an OSError if the connection fails within timeout_ms.
        `feed` is an optional callback (e.g. watchdog feed) called while waiting.

        Each call restarts the interface then lets the driver retry the association by itself
        (failed WPA handshakes are common with a weak signal); the caller retries on failure.
        """
        if self._wlan.isconnected():
            return

        print("Connecting to WiFi...")
        self._reset_interface()
        try:
            self._wlan.connect(self.ssid, self.password)
        except OSError as e:
            raise OSError(f"WiFi connect call failed: {e}")

        start_time = time.ticks_ms()
        while not self._wlan.isconnected() and time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
            if feed:
                feed()
            time.sleep(0.5)

        if not self._wlan.isconnected():
            raise OSError(f"Failed to connect to WiFi network (status={self._wlan.status()}).")

        elapsed_s = time.ticks_diff(time.ticks_ms(), start_time) // 1000
        print(f"WiFi connected successfully in {elapsed_s}s.")
        print("IP Address:", self._wlan.ifconfig()[0])

    def is_connected(self) -> bool:
        """Returns True if currently connected to the WiFi network."""
        return self._wlan.isconnected()

    def disconnect(self):
        """Disconnects from the WiFi network if connected."""
        if self._wlan.isconnected():
            self._wlan.disconnect()
