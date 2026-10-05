import json
import socket
import ssl

from umqtt.simple import MQTTClient, MQTTException


class _MQTTClient(MQTTClient):
    """
    MQTTClient hardened for weak WiFi links:
    - counts unanswered pings, to detect a silently dead connection;
    - keeps a timeout on the socket, so a read/write on a dead link raises OSError instead of blocking forever
      (upstream umqtt switches the socket back to fully blocking mode after each read).
    Note: umqtt.simple is frozen in the MicroPython firmware, so it cannot be patched in lib/.
    """

    pings_pending = 0
    _raw_sock = None
    _broker_addr = None

    def connect(self, clean_session=True, timeout=None):
        self.pings_pending = 0
        self.socket_timeout = timeout
        # Same as upstream connect(), but keeps a reference on the raw socket:
        # SSLSocket has no settimeout(), the timeout must be set on the underlying socket
        self._raw_sock = socket.socket()
        self._raw_sock.settimeout(timeout)
        self.sock = self._raw_sock
        try:
            addr = socket.getaddrinfo(self.server, self.port)[0][-1]
            self._broker_addr = addr
        except OSError:
            # DNS lookups often fail on a weak link: reuse the last resolved address if any
            if self._broker_addr is None:
                raise
            addr = self._broker_addr
        self.sock.connect(addr)
        if self.ssl is True:
            self.sock = ssl.wrap_socket(self.sock, **self.ssl_params)
        elif self.ssl:
            self.sock = self.ssl.wrap_socket(self.sock, server_hostname=self.server)
        premsg = bytearray(b"\x10\0\0\0\0\0")
        msg = bytearray(b"\x04MQTT\x04\x02\0\0")

        sz = 10 + 2 + len(self.client_id)
        msg[6] = clean_session << 1
        if self.user:
            sz += 2 + len(self.user) + 2 + len(self.pswd)
            msg[6] |= 0xC0
        if self.keepalive:
            assert self.keepalive < 65536
            msg[7] |= self.keepalive >> 8
            msg[8] |= self.keepalive & 0x00FF
        if self.lw_topic:
            sz += 2 + len(self.lw_topic) + 2 + len(self.lw_msg)
            msg[6] |= 0x4 | (self.lw_qos & 0x1) << 3 | (self.lw_qos & 0x2) << 3
            msg[6] |= self.lw_retain << 5

        i = 1
        while sz > 0x7F:
            premsg[i] = (sz & 0x7F) | 0x80
            sz >>= 7
            i += 1
        premsg[i] = sz

        self.sock.write(premsg, i + 2)
        self.sock.write(msg)
        self._send_str(self.client_id)
        if self.lw_topic:
            self._send_str(self.lw_topic)
            self._send_str(self.lw_msg)
        if self.user:
            self._send_str(self.user)
            self._send_str(self.pswd)
        resp = self.sock.read(4)
        assert resp[0] == 0x20 and resp[1] == 0x02
        if resp[3] != 0:
            raise MQTTException(resp[3])
        return resp[2] & 1

    def ping(self):
        super().ping()
        self.pings_pending += 1

    def wait_msg(self):
        res = self.sock.read(1)
        # Back to blocking mode, but with a timeout (upstream uses setblocking(True), i.e. no timeout)
        self._raw_sock.settimeout(self.socket_timeout)
        if res is None:
            return None
        if res == b"":
            raise OSError(-1)
        if res == b"\xd0":  # PINGRESP
            sz = self.sock.read(1)[0]
            assert sz == 0
            self.pings_pending = 0
            return None
        op = res[0]
        if op & 0xF0 != 0x30:
            return op
        sz = self._recv_len()
        topic_len = self.sock.read(2)
        topic_len = (topic_len[0] << 8) | topic_len[1]
        topic = self.sock.read(topic_len)
        sz -= topic_len + 2
        if op & 6:
            pid = self.sock.read(2)
            pid = pid[0] << 8 | pid[1]
            sz -= 2
        msg = self.sock.read(sz)
        self.cb(topic, msg)
        if op & 6 == 2:
            pkt = bytearray(b"\x40\x02\0\0")
            pkt[2] = pid >> 8
            pkt[3] = pid & 0xFF
            self.sock.write(pkt)
        elif op & 6 == 4:
            assert 0
        return op


class MqttManager:
    KEEPALIVE_S = 60  # Broker drops the client if it hears nothing for 1.5 x this delay
    MAX_PINGS_PENDING = 3  # Tolerates slow answers on a weak WiFi link

    def __init__(self, client_id: str, host: str, port: int, username: str, password: str):
        self.client_id = client_id

        # Initialize TLS MQTT client
        self._client = _MQTTClient(
            client_id=client_id,
            server=host,
            port=port,
            user=username,
            password=password,
            ssl=True,
            ssl_params={},
            keepalive=self.KEEPALIVE_S,
        )

    def connect(self, timeout: int = 8):
        """
        Connects to the MQTT broker.
        The socket timeout (seconds) prevents the TLS handshake from blocking forever.
        Exceptions raised by umqtt will propagate automatically.
        """
        print("Connecting to MQTT broker...")
        self._client.connect(timeout=timeout)
        print("MQTT connected successfully.")

    def set_callback(self, message_callback):
        """
        Sets the callback function for subscribed topics.
        """
        self._client.set_callback(message_callback)
        print("Add callback for subscribed topics")

    def subscribe(self, topic: str):
        """
        Subscribes to a specific topic.
        """
        self._client.subscribe(topic)
        print(f"Subscribed to topic: {topic}")

    def unsubscribe(self, topic: str):
        """
        Unsubscribes to a specific topic.
        """
        self._client.unsubscribe(topic)
        print(f"Unsubscribed to topic: {topic}")

    def publish(self, topic: str, payload: dict, retain: bool = False):
        """
        Publishes a JSON-encoded payload to a specific topic.
        """
        self._client.publish(topic, json.dumps(payload).encode("utf-8"), retain=retain)

    def check_for_messages(self):
        """
        Checks for pending messages.
        Will raise an OSError if the socket is dead.
        """
        self._client.check_msg()

    def ping(self):
        """
        Sends a Keep-Alive ping to the MQTT broker.
        Raises an OSError if the previous pings were never answered (silently dead connection).
        """
        if self._client.pings_pending >= self.MAX_PINGS_PENDING:
            raise OSError("MQTT broker not answering pings")
        self._client.ping()

    def disconnect(self):
        """
        Gracefully disconnects the MQTT client.
        Errors are ignored here because this is usually called to clean up
        an already broken connection.
        """
        try:
            self._client.disconnect()
        except Exception:
            pass
        # Always release the socket, even if the DISCONNECT packet could not be sent
        if self._client.sock:
            try:
                self._client.sock.close()
            except Exception:
                pass
            self._client.sock = None
