import asyncio
import logging
from bleak import BleakScanner, BleakClient, BleakError

logger = logging.getLogger(__name__)


def signed(char):
    return char - 256 if char > 127 else char


class MarioController:
    BLE_Name = "LEGO Mario"
    LEGO_HUB_UUID =            "00001623-1212-efde-1623-785feabcd123"
    LEGO_CHARACTERISTIC_UUID = "00001624-1212-efde-1623-785feabcd123"
    #SUBSCRIBE_IMU_COMMAND = bytearray([0x0A, 0x00, 0x41, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00, 0x01])
    #SUBSCRIBE_RGB_COMMAND = bytearray([0x0A, 0x00, 0x41, 0x01, 0x00, 0x05, 0x00, 0x00, 0x00, 0x01])
    #SUBSCRIBE_CLO_COMMAND = bytearray([0x0A, 0x00, 0x41, 0x02, 0x00, 0x05, 0x00, 0x00, 0x00, 0x01])
    SUBSCRIBE_IMU_COMMAND = bytearray([0x0A, 0x00, 0x41, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01])
    SUBSCRIBE_RGB_COMMAND = bytearray([0x0A, 0x00, 0x41, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01])
    SUBSCRIBE_CLO_COMMAND = bytearray([0x0A, 0x00, 0x41, 0x02, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01])

    CALLBACK_TYPES = {'color', 'tile', 'pants', 'movement'}

    DEBUG_SCANNER = 0b001
    DEBUG_MOVEMENT = 0b010
    DEBUG_OTHER = 0b100

    colors = {
        0x0c01: 'purple',
        0x1300: 'white',
        0x1500: 'red',
        0x1700: 'blue',
        0x1800: 'yellow',
        0x2500: 'green',
        0x3801: 'brown',
        0x4201: 'cyan',
        0x6a00: 'orange',
        0x1a00: 'black',
    }

    tiles = {
        0x2: 'gumba',
        0x4: 'timer_30',
        0x10: 'cyclical_1',
        0x15: 'timer_30_2',
        0x14: 'cyclical_2', # nxt - obroty
        0x20: 'heart',
        0x21: 'one',  # mashroom 1
        0x23: 'blue_mushroom',  # minimizes Mario
        0x29: 'surprise',  # question mark
        0x2e: 'cloud', # flying on the cloud
        0x3c: 'stop_platform',
        0x5d: 'talk',
        0x63: 'custom_tree',
        0x7b: 'star',
        0x7d: 'code 6',
        0x80: 'surprise_3', # rozowy
        0x88: '??',
        0x89: 'fish',       # nxt - ryby
        0x8b: 'bowser_junior_fight',
        0x8c: 'peach',
        0x90: 'timer_10',
        0x96: 'bowser_senior_fight',
        0x99: 'bowser_junior',
        0x1d: 'bowser_senior',
        0x2c: 'moving_platform',
        #0xb5: 'stop_platform',
        0xb7: 'goal', # meta
        0xb8: 'start',
        0xbe: 'spider',
    }

    sounds = {
        'set1': {
            'background_slow': 'course_free',
            'background_fast': 'Chijou Fast',
            'star': 'Star Drc',
            'fight': 'Hikousen Fast',
            'failed': 'Down',
            'small_win': 'Cheepfanfare Lr Ry 32',
            'big_win': 'big_win',
            'died': 'Down',
            'end': 'Course Clear',
            'end2': 'end_free',
            'shot': 'Speed Up',
            'bowser_dies': 'Hikousenboss Crear',
            'coin': 'coin',
            'fight_back': 'bowser_laugh',
        },
        'set2': {
            'background_slow': '403372__emceeciscokid__chiptune-melody.ogg',
            'background_fast': '',
            'star': 'Star Drc',
            'fight': 'Hikousen Fast',
            'failed': 'Down',
            'small_won': 'Cheepfanfare Lr Ry 32',
            'big_won': 'BGM Last Boss Fanfare Lr Ry 32',
            'died': 'Down',
            'end': 'Course Clear',
            'shot': 'Speed Up',
            'bowser_dies': 'Hikousenboss Crear',
            'coin': 'Coin Win',
        }

    }

    def __init__(self, ble_address=None, volume=0, debug_level=0):
        self.color_callback = None
        self.tile_callback = None
        self.move_callback = None
        self.color = None
        self.tile = None
        self.current_x = 0
        self.current_y = 0
        self.current_z = 0
        self.devices = []
        self.client = None
        self.ble_address = ble_address
        self.volume = volume
        self.debug_level = debug_level
        self.callbacks = dict.fromkeys(self.CALLBACK_TYPES)

    @classmethod
    def get_tile(cls, id):
        if id in cls.tiles:
            return cls.tiles[id]
        else:
            return 'unknown'

    @classmethod
    def get_color(cls, id):
        if id in cls.colors:
            return cls.colors[id]
        else:
            return '-'

    async def set_volume(self, level):
        await self.client.write_gatt_char(
            self.LEGO_CHARACTERISTIC_UUID,
            bytearray([0x06, 0x00, 0x01, 0x12, 0x01, level])
        )

    async def notification_handler(self, sender, data):

        if data[0] == 0x8:  # scanner information
            if self.debug_level & self.DEBUG_SCANNER:
                print(" Scanner: " + " ".join(hex(n) for n in data))
            if data[5] == 0x0:  # tile detected
                if data[4] in self.tiles:
                    logger.debug(f'\t Tile: {self.tiles[data[4]]}')
                    for callback in self.callbacks['tile']:
                        await callback(self.tiles[data[4]])
                        await asyncio.sleep(0.1)
                else:
                    logger.info(f'Unknown tile ({hex(data[4])})')
            else:  # color detected
                color = int.from_bytes(data[6:8], byteorder='big')
                if color in self.colors:
                    logger.debug(f'\t Color: {self.colors[color]}')
                    for callback in self.callbacks['color']:
                        await callback(self.colors[color])
                        await asyncio.sleep(0.1)
                else:
                    logger.info(f'Unknown color ({hex(data[6])})')

        elif data[0] == 0x7:  # movement information
            if self.debug_level & self.DEBUG_MOVEMENT:
                print('                   ', end='\r')
                print(" Movement: " + " ".join(str(signed(n)) for n in data[4:]), end='')
            for callback in self.callbacks['movement']:
                await callback(signed(data[4]), signed(data[5]), signed(data[6]))
                await asyncio.sleep(0.1)

        else:
            if self.debug_level & self.DEBUG_OTHER:
                print(" Other: " + " ".join(hex(n) for n in data))

    async def find(self, timeout=10) -> str:
        try:
            scanner = BleakScanner(filters={"UUIDs": [self.LEGO_HUB_UUID], "DuplicateData":False})
            self.devices = await scanner.discover(timeout)
            for d in self.devices:
                if d.name.strip() == self.BLE_Name and self.LEGO_HUB_UUID in d.metadata["uuids"]:
                    self.client = d
                    print("Found Mario :)")
                    return d.address
        except BleakError as e:
            raise Exception("Bluetooth error: ", e)

        raise Exception("Mario not found!")

    async def connect(self, timeout=5):
        if self.ble_address:
            address = self.ble_address
        else:
            address = await self.find(timeout)

        try:
            async with BleakClient(address) as client:
                self.client = client
                if not client.is_connected:
                    await client.connect()
                if client.is_connected:
                    logger.debug(f'Mario is connected. {client.address}')
                await self.set_volume(self.volume)
                await asyncio.sleep(0.1)
                await client.start_notify(self.LEGO_CHARACTERISTIC_UUID, self.notification_handler)
                await asyncio.sleep(0.1)
                await client.write_gatt_char(self.LEGO_CHARACTERISTIC_UUID, self.SUBSCRIBE_IMU_COMMAND)
                await asyncio.sleep(0.1)
                await client.write_gatt_char(self.LEGO_CHARACTERISTIC_UUID, self.SUBSCRIBE_RGB_COMMAND)
                await asyncio.sleep(0.1)
                await client.write_gatt_char(self.LEGO_CHARACTERISTIC_UUID, self.SUBSCRIBE_CLO_COMMAND)
                while self.client.is_connected:
                    await asyncio.sleep(1)
        except Exception as e:
            logger.exception("Could not connect to Mario", e)

    def register_callback(self, callback, callback_types: set = None):
        if not callback_types:
            callback_types = self.CALLBACK_TYPES
        for callback_type in callback_types:
            logger.debug(f'Registering callback: {callback.__name__} for event: {callback_type}')
            if not self.callbacks[callback_type]:
                self.callbacks[callback_type] = [callback]
            else:
                self.callbacks[callback_type].append(callback)
        return

    def disconnect(self):
        self.client.disconnect()


