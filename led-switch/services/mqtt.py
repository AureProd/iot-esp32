import json

from umqtt.simple import MQTTClient


class MqttManager:
    def __init__(self, client_id: str, host: str, port: int, username: str, password: str):
        self.client_id = client_id

        # Initialize TLS MQTT client
        self._client = MQTTClient(
            client_id=client_id, server=host, port=port, user=username, password=password, ssl=True, ssl_params={}
        )

    def connect(self):
        """
        Connects to the MQTT broker.
        Exceptions raised by umqtt will propagate automatically.
        """
        print("Connecting to MQTT broker...")
        self._client.connect()
        print("MQTT connected successfully.")

    def subscribe(self, topic: str, message_callback):
        """
        Sets the callback and subscribes to a specific topic.
        """
        self._client.set_callback(message_callback)
        self._client.subscribe(topic)
        print(f"Subscribed to topic: {topic}")

    def publish(self, topic: str, payload: dict):
        """
        Publishes a JSON-encoded payload to a specific topic.
        """
        self._client.publish(topic, json.dumps(payload))

    def check_for_messages(self):
        """
        Checks for pending messages.
        Will raise an OSError if the socket is dead.
        """
        self._client.check_msg()

    def ping(self):
        """
        Sends a Keep-Alive ping to the MQTT broker.
        Will raise an OSError if the broker doesn't respond.
        """
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
