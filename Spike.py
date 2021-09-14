from bluedot.btcomm import BluetoothClient
from dataclasses import dataclass, asdict
import base64
import json
import logging
import asyncio
import time

logger = logging.getLogger(__name__)


@dataclass
class RPC:
    cmd: {}
    cls: str = 'motor'
    port: str = 'A'


class Spike:

    def __init__(self, hub_name='LEGO Hub@MarioSpike'):
        self.read_callback = None
        try:
            self.spike = BluetoothClient(hub_name, self.data_handler)
            #time.sleep(1)
            #self.spike.send('\x03')
        except Exception as e:
            logger.exception(e)

    def add_read_callback(self, callback):
        self.read_callback = callback

    def data_handler(self, data):
        if self.read_callback:
            self.read_callback(data)

    def cmd(self, rpc: RPC):
        json_rpc = json.dumps(asdict(rpc))
        logger.debug(f'spike rpc: {json_rpc}')
        self.spike.send(json_rpc)

    def calibrate(self):
        try:
            rpc = RPC(cls='calibrate', cmd={})
            self.cmd(rpc)
            time.sleep(2)
        except Exception as e:
            logger.exception(e)

    def to_position(self, position, port='A'):
        rpc = RPC(cls='to_position', port=port, cmd={'position': position})
        self.cmd(rpc)

    def shake(self, port='A'):
        rpc = RPC(cls='shake', cmd={})
        self.cmd(rpc)

    def success(self):
        rpc = RPC(cls='success', cmd={})
        self.cmd(rpc)

