import asyncio
import logging
import sys
import time
from typing import Callable
import pytest
from functools import partial
from threading import Event
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.client import Client
from common.IceRunnerConfiguration import IceRunnerConfiguration
from raspberry.mqtt.handlers import MqttClient, add_handlers


logger = logging.getLogger()
logger.level = logging.DEBUG


class MQTTClient:
    def __init__(self):
        self.client = Client(CallbackAPIVersion.VERSION2, client_id="test")
        self.client.connect("localhost", 1883)
        self.client.loop_start()  # Start network loop in a separate thread
        self.client.subscribe("ice_runner/#")

    def publish_message(self, topic, payload):
        self.client.publish(topic, payload)

    def stop(self):
        self.client.loop_stop()

class BaseTest():
    def setup_method(self, test_method):
        self.mqtt = MQTTClient()
        self.make_config()
        MqttClient.configuration = IceRunnerConfiguration(dict_conf=self.config_dict)

        self.stream_handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(self.stream_handler)

    def teardown_method(self, test_method):
        self.mqtt.stop()
        self.mqtt.client.disconnect()
        logger.removeHandler(self.stream_handler)

    def make_config(self):
        config = {}
        for name in IceRunnerConfiguration.attribute_names:
            config[name] = {}
            for component in IceRunnerConfiguration.components:
                config[name][component] = ""
            config[name]["type"] = "int"
            config[name]["value"] = 1
        self.config_dict = config

    async def wait_for_bool(self, expression: Callable, timeout: float = 3) -> bool:
        start_time = time.time()
        while (not expression()) and (time.time() - start_time < timeout):
            await asyncio.sleep(0.1)
        if expression():
            return True
        return False

class TestZeroConfiguration(BaseTest):
    def setup_method(self, test_method):
        super().setup_method(test_method)
        MqttClient.connect(-100, "localhost", 1883)
        add_handlers()
        asyncio.run(MqttClient.start())

    def create_a_callback(self):
        def callback(client, userdata, message, event: Event, expected_value=None):
            del userdata, client
            if expected_value is not None:
                assert message.payload.decode() == expected_value
            event.set()
        return callback

    def add_callback(self, callback_called, topic: str, expected_msg=None):
        callback = self.create_a_callback()

        self.mqtt.client.message_callback_add(
            topic, partial(callback, event=callback_called, expected_value=expected_msg)
        )
        self.mqtt.client.subscribe(topic)

    def test_who_alive(self):
        callback_called = Event()

        self.add_callback(callback_called, "ice_runner/raspberry_pi/#")
        self.mqtt.client.loop_start()

        # Publish test message
        self.mqtt.publish_message("ice_runner/server/rp_commander/who_alive", "who_alive_test")
        logging.info(f"MqttClient.state {MqttClient.state}")
        # Wait for callback, with a timeout to avoid infinite wait
        callback_result = callback_called.wait(timeout=3)
        assert callback_result, f"The callback was not called as expected."

    def test_rp_status(self):
        status_called = Event()
        MqttClient.status = {"Helo": "World"}
        self.add_callback(status_called, "ice_runner/raspberry_pi/+/status")
        self.mqtt.client.loop_start()

        self.mqtt.publish_message(
            f"ice_runner/server/rp_commander/{MqttClient.run_id}/command", "status")
        # Wait for callback, with a timeout to avoid infinite wait
        callback_result = status_called.wait(timeout=4.0)
        assert callback_result, f"The callback was not called as expected."

    @pytest.mark.asyncio
    async def test_start_command(self):
        self.mqtt.client.publish(
            f"ice_runner/server/rp_commander/{MqttClient.run_id}/command", "start")
        # Wait for callback, with a timeout to avoid infinite wait
        flag_exp = lambda: MqttClient.to_run
        flag_result = await self.wait_for_bool(flag_exp, timeout=3)
        assert flag_result, f"The callback was not called as expected."

    @pytest.mark.asyncio
    async def test_stop_command(self):
        self.mqtt.client.publish(
            f"ice_runner/server/rp_commander/{MqttClient.run_id}/command", "stop")
        # Wait for callback, with a timeout to avoid infinite wait
        flag_exp = lambda: MqttClient.to_stop
        flag_result = await self.wait_for_bool(flag_exp, timeout=3)
        assert flag_result, f"The callback was not called as expected."

    @pytest.mark.asyncio
    async def test_keep_alive(self):
        last_keep_alive = MqttClient.last_message_receive_time
        self.mqtt.client.publish(
            f"ice_runner/server/rp_commander/{MqttClient.run_id}/command", "keep alive")

        flag_exp = lambda: MqttClient.last_message_receive_time != last_keep_alive
        logging.info(flag_exp())
        flag_result = await self.wait_for_bool(flag_exp, timeout=3)
        assert flag_result, f"The callback was not called as expected."

    def test_full_configuration(self):
        callback_called = Event()
        self.add_callback(callback_called, "ice_runner/raspberry_pi/+/full_config")
        self.mqtt.client.loop_start()

        self.mqtt.publish_message(
            f"ice_runner/server/rp_commander/{MqttClient.run_id}/command", "full_config")
        # Wait for callback, with a timeout to avoid infinite wait
        callback_result = callback_called.wait(timeout=4.0)
        assert callback_result, f"The callback was not called as expected."


if __name__ == "__main__":
    pytest.main()
