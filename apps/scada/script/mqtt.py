import base64
import logging
import signal
import threading
import urllib.parse
from typing import Any

import click
from paho.mqtt import client as mqtt
from pydantic import BaseModel, Extra, Field
import requests

from apps.scada.utils.grm.client import GrmClient
from apps.scada.utils.grm.schemas import GrmVariable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GrmMqttService(BaseModel):
    broker: str = Field(default="localhost")
    port: int = Field(default=1883)
    manager_port: int = Field(default=18083)
    manager_username: str
    manager_secret: str
    module_number: str
    module_secret: str
    module_url: str = Field(default="http://www.yunplc.com:7080")
    freq: int = Field(default=3)
    keepalive: bool = Field(default=False)

    class Config:
        extra = Extra.allow

    def _start_timer(self):
        self._timer = threading.Timer(self.freq, self._read_and_publish)
        self._timer.start()

    def _get_subscriptions(self) -> list[GrmVariable]:
        headers = {
            "Authorization": self._manager_token,
            "Content-Type": "application/json",
        }
        response = requests.get(self._manager_url, headers=headers, timeout=3)

        if response.status_code != 200:
            logger.error(f"Failed to get subscriptions: {response.text}")
            return []

        variables: list[GrmVariable] = []
        topic_subscripted: set[str] = set()
        data = response.json()
        for result in data["data"]:
            topic = result["topic"]
            if topic in topic_subscripted:
                continue
            topic_subscripted.add(topic)

            if topic.startswith(self._topic_root):
                variable_path = topic[len(self._topic_root) :]
                if "/" in variable_path:
                    group, variable_name = variable_path.split("/")
                else:
                    group = ""
                    variable_name = variable_path
                grm_var = GrmVariable(
                    module_number=self.module_number,
                    name=variable_name,
                    group=group,
                    type="F",
                    rw=False,
                    priority=0,
                    desc="",
                    value=0.0,
                    write_error=0,
                    read_error=0,
                )
                variables.append(grm_var)
        return variables

    def _read_and_publish(self):
        try:
            variables = self._get_subscriptions()
            if not variables:
                return
            self._grm.read(variables)

            for v in variables:
                if v.read_error:
                    logger.error(f"Error reading variable {v.name}: {v.read_error}")
                    continue
                if len(v.group) > 0:
                    topic = f"{self._topic_root}{v.group}/{v.name}"
                else:
                    topic = f"{self._topic_root}{v.name}"
                self._mqtt.publish(topic, v.value)

        except Exception as e:
            logger.error(f"Error reading from GRM client or publishing to MQTT: {e}")
        finally:
            # 重启定时器
            if self._running:
                self._start_timer()

    def serve(self):
        self._topic_root = (
            f"hetu/datasource/freq_{self.freq}/module_{self.module_number}/"
        )
        self._command_root = f"hetu/datasource/command/module_{self.module_number}/"
        self._manager_token = (
            "Basic "
            + base64.b64encode(
                (self.manager_username + ":" + self.manager_secret).encode()
            ).decode()
        )
        params = urllib.parse.urlencode({"match_topic": f"{self._topic_root}#"})
        self._manager_url = (
            f"http://{self.broker}:{self.manager_port}/api/v5/subscriptions?{params}"
        )
        self._subscribed_vars: list[GrmVariable] = []

        # 连接MQTT
        client = mqtt.Client()
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.connect(self.broker, self.port, 60)
        client.subscribe(f"{self._command_root}#", 2)  # qos=2
        self._mqtt = client

        # 连接GRM
        grm_client = GrmClient(self.module_number, self.module_secret, self.module_url)
        grm_client.connect()
        self._grm = grm_client

        self._running = True
        self._start_timer()
        self._mqtt.loop_forever()

    def stop(self):
        self._mqtt.disconnect()
        self._mqtt.loop_stop()
        self._running = False
        self._timer.cancel()

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, rc: int):
        logger.info("Connected with result code " + str(rc))

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int):
        logger.info("Disconnected with result code " + str(rc))

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage):
        try:
            value = float(msg.payload.decode())
            if msg.topic.startswith(self._command_root):
                variable_path = msg.topic[len(self._command_root) :]
                if "/" in variable_path:
                    group, variable_name = variable_path.split("/")
                else:
                    group = ""
                    variable_name = variable_path
                grm_var = GrmVariable(
                    module_number=self.module_number,
                    name=variable_name,
                    group=group,
                    type="F",
                    rw=True,
                    priority=0,
                    desc="",
                    value=value,
                    write_error=0,
                    read_error=0,
                )
                self._grm.write([grm_var])
                if grm_var.write_error:
                    logger.error(
                        f"Error writing variable {grm_var.name}: {grm_var.write_error}"
                    )
                else:
                    logger.info(f"Written topic {msg.topic} with value {value}")
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")


@click.command()
@click.option(
    "--broker",
    envvar="BROKER",
    type=str,
    required=True,
    help="MQTT broker address",
)
@click.option(
    "--port",
    envvar="PORT",
    type=int,
    default=1883,
    help="MQTT port",
)
@click.option(
    "--manager-port",
    type=int,
    default=18083,
    help="Broker Management API port",
)
@click.option(
    "--manager-username",
    envvar="MANAGER_USERNAME",
    required=True,
    type=str,
    help="Broker Management API username",
)
@click.option(
    "--manager-secret",
    envvar="MANAGER_SECRET",
    required=True,
    type=str,
    help="Broker Management API secret",
)
@click.option(
    "--module-number",
    envvar="MODULE_NUMBER",
    required=True,
    type=str,
    help="Module Number",
)
@click.option(
    "--module-secret",
    envvar="MODULE_SECRET",
    required=True,
    type=str,
    help="Module secret",
)
@click.option(
    "--module-url",
    envvar="MODULE_URL",
    required=True,
    type=str,
    help="Module URL",
)
def main(
    broker: str,
    port: int,
    manager_port: int,
    manager_username: str,
    manager_secret: str,
    module_number: str,
    module_secret: str,
    module_url: str,
) -> None:
    service = GrmMqttService(
        broker=broker,
        port=port,
        manager_port=manager_port,
        manager_username=manager_username,
        manager_secret=manager_secret,
        module_number=module_number,
        module_secret=module_secret,
        module_url=module_url,
    )

    def signal_handler(sig, frame):
        logger.info("Signal received, stopping...")
        service.stop()

    # 注册信号处理函数
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    service.serve()


if __name__ == "__main__":
    main()
