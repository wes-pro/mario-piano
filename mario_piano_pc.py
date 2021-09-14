import asyncio
from bluedot.btcomm import BluetoothClient
from MarioController import MarioController
from Spike import Spike
import logging.config
import pygame.midi
from mido import MidiFile
import sys
import functools
import signal
import base64
import json

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)

pygame.midi.init()
player = pygame.midi.Output(0)


async def signal_handler(signo, loop):
    logger.debug('caught {0}'.format(signo.name))
    for task in asyncio.all_tasks():
        if task is asyncio.tasks.current_task():
            continue
        task.cancel()
    await asyncio.sleep(2)
    raise KeyboardInterrupt

tunes = {
    'twinkle': {
        'shift_notes': -5,
        'crotchet_duration': 1,
        'scores': [
            'G0', 'G0', 'D', 'D', 'E', 'E', 'D', '-',
            'C', 'C', 'B0', 'B0', 'A0', 'A0', 'G0', '-',
            'D', 'D', 'C', 'C', 'B0', 'B0', 'A0', '-',
            'D', 'D', 'C', 'C', 'B0', 'B0', 'A0', '-',
            'G0', 'G0', 'D', 'D', 'E', 'E', 'D', '-',
            'C', 'C', 'B0', 'B0', 'A0', 'A0', 'G0', '-',
        ]
    },
    'shark': {
        'shift_notes': 0,
        'crotchet_duration': 0.35,
        'scores': [
            'D', '---', 'E', '---', 'G', '---', 'G', '---', 'G', '---', 'G', 'G', '---', 'G', '----',
            'D', '---', 'E', '---', 'G', '---', 'G', '---', 'G', '---', 'G', 'G', '---', 'G', '----',
            'D', '---', 'E', '---', 'G', '---', 'G', '---', 'G', '---', 'G', 'G', '---', 'G', '----',
            'G', '---', 'G', '---', 'F#', '----', '----'
            'D', '---', 'E', '---', 'G', '---', 'G', '---', 'G', '---', 'G', 'G', '---', 'G', '----',
            'D', '---', 'E', '---', 'G', '---', 'G', '---', 'G', '---', 'G', 'G', '---', 'G', '----',
            'D', '---', 'E', '---', 'G', '---', 'G', '---', 'G', '---', 'G', 'G', '---', 'G', '----',
            'G', '---', 'G', '---', 'F#', '---'
        ]
    },
    'incy': {
        'shift_notes': 0,
        'crotchet_duration': 0.4,
        'scores': [
            'C', '-', 'C', '-', 'C', '--', 'D', '-', 'E', '---', 'E', '--',
            'E', '-', 'D', '--', 'C', '-', 'D', '--', 'E', '-', 'C', '----',
            'E', '---', 'E', '--', 'F', '-', 'G', '---',
            'G', '---', 'F', '--', 'E', '-', 'F', '--', 'G', '-', 'E', '----',
            'C', '---', 'C', '--', 'D', '-', 'E', '---', 'E', '---',
            'D', '--', 'C', '-', 'D', '--', 'E', '-', 'C', '---',
            'C', '---', 'C', '--', 'C', '-',  'C', '--',  'D', '-', 'E', '---', 'E', '--',
            'E', '-', 'D', '--', 'C', '-',  'D', '--', 'E', '-', 'C', '---'
        ]
    },
}

tune = 'stop'
teach = False
cmd = ''
stop_playing = False

shift_notes = 0
notes_to_pitch = {
    'C0': 48, 'D0': 50, 'E0': 52, 'F0': 53, 'G0': 55, 'A0': 57, 'B0': 59,
    'C': 60, 'D': 62, 'E': 64, 'F': 65, 'G': 67, 'A': 69, 'B': 71,
    'C1': 72, 'D1': 74, 'E1': 76, 'F1': 77, 'G1': 79, 'A1': 81, 'B1': 83
}
pitch_to_note = {p: n for n, p in notes_to_pitch.items()}

colors_to_notes = {'brown': 'C', 'red': 'D', 'orange': 'E', 'yellow': 'F', 'green': 'G',
                   'cyan': 'A', 'blue': 'B', 'purple': 'C1'}
notes_to_colors = {n: c for c, n in colors_to_notes.items()}

keys = ['brown', 'red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'purple']

tiles_to_instruments = {
    'surprise': 117,     # perkusja
    'goal': 113,        # perkusja 2
    'one': 72,           #64,          # trabka
    'spider': 68,          # trabka
    'fish': 0,         # piano
    'heart': 19,        # church organ
    'talk': 25,         # guitar
    'stop_platform': 29,  # guitar 1
}

spike = Spike()

minimal_duration = 1
crotchet_duration = 1      # ćwierćnuta - długość bazowa
current_instrument = 0
player.set_instrument(current_instrument)
previous_note = None
expected_note = None
expected_note_played = False


def receive_data(data):
    global tune
    global cmd
    global stop_playing
    try:
        msg = json.loads(data)
        tune = msg['song']
        cmd = msg['cmd']
        logger.debug(f'Received cmd "{cmd}", song: {tune}')
        if tune == 'stop':
            stop_playing = True
        #if msg['cmd'] == 'double_tapped':
        #    tune = msg['song']
    except Exception as e:
        #print(f'Unrecognized data: X{data}X')
        #logger.exception(e)
        #logger.debug(f'Unrecognized data: X{data}X')
        pass


async def play_tune(tune, mode=None):
    global expected_note
    global expected_note_played
    global teach
    global stop_playing
    spike.calibrate()
    try:
        if tune in tunes:
            stop_playing = False
            shift = tunes[tune]['shift_notes']
            scores = tunes[tune]['scores']
            crotchet_duration = tunes[tune]['crotchet_duration']
            for n in scores:
                if stop_playing:
                    return
                _modifier = 0
                if '#' in n:
                    _modifier = 1
                    n = n[0]
                if 'b' in n:
                    _modifier = -1
                    n = n[0]

                if mode == 'point' and '-' not in n:
                    await point_note(pitch_to_note[notes_to_pitch[n] - shift])
                elif mode == 'teach' and '-' not in n:
                    try:
                        expected_note = notes_to_pitch[pitch_to_note[notes_to_pitch[n] - shift]]
                        logger.debug(f'setting expected note to: {n} (value after shift: {expected_note})')
                        await point_note(pitch_to_note[notes_to_pitch[n] - shift])
                    except Exception as e:
                        logger.exception(e)

                    while True:
                        #logger.debug('teaching loop...')
                        await asyncio.sleep(0.3)
                        if expected_note_played or stop_playing:
                            expected_note_played = False
                            break

                if '-' in n:
                    await asyncio.sleep(crotchet_duration * len(n.split('-'))-1)
                else:
                    player.note_on(notes_to_pitch[n] + shift + _modifier, 127)
                    await asyncio.sleep(crotchet_duration)
                    player.note_off(notes_to_pitch[n] + shift + _modifier, 127)

                await asyncio.sleep(0.1)
    except Exception as e:
        logger.exception(e)
    finally:
        #await asyncio.sleep(2)
        spike.success()
        spike.calibrate()


async def point_note(note):
    logger.debug(f'point_note {note}')
    global previous_note
    if note == '-':
        return
    try:
        if previous_note and previous_note == note:
            spike.shake()
        else:
            _position = keys.index(notes_to_colors[note])
            logger.debug(f'to_position: {_position}')
            spike.to_position(_position)

    except Exception as e:
        logger.exception(e)
    finally:
        previous_note = note


async def tune_change():
    global tune
    global teach
    global cmd
    while True:
        await asyncio.sleep(1)
        if cmd == 'play':
            logger.debug(f'Play tune: X{tune}X')
            await play_tune(tune, mode='point')
        elif cmd == 'teach' and tune != 'stop':
            teach = True
            logger.debug(f'Teach tune: X{tune}X')
            await play_tune(tune, mode='teach')
            teach = False
        cmd = ''


async def color_handler(color):
    global expected_note
    global expected_note_played
    global teach
    if color in ['white', '-']:
        return
    if color in colors_to_notes:
        logger.debug(f'teach mode: {teach}')
        if teach:
            logger.debug(f'expect note value: {expected_note + shift_notes}')
            logger.debug(f'actual note value: {notes_to_pitch[colors_to_notes[color]]}')
            if expected_note != notes_to_pitch[colors_to_notes[color]]+shift_notes:
                return
            else:
                expected_note_played = True
                expected_note = False
        else:
            player.note_on(notes_to_pitch[colors_to_notes[color]]+shift_notes, 127)
            await asyncio.sleep(crotchet_duration)
            player.note_off(notes_to_pitch[colors_to_notes[color]]+shift_notes, 127)


async def tile_handler(tile):
    if tile in tiles_to_instruments:
        player.set_instrument(tiles_to_instruments[tile])


async def async_main():
    global start_position
    spike.add_read_callback(receive_data)
    mario = MarioController(
        ble_address="E4:E1:12:DF:DF:3E",
        volume=0,
        debug_level=MarioController.DEBUG_SCANNER | MarioController.DEBUG_OTHER
    )
    mario.register_callback(color_handler, {'color'})
    mario.register_callback(tile_handler, {'tile'})
    await mario.connect()


async def async_main2():
    try:
        spike.add_read_callback(receive_data)
        #spike.calibrate()
        #await play_tune('twinkle', mode='point')
        #await play_tune('spider')

    except Exception as e:
        logger.exception(e)


async def async_main3():
    #await play_tune('twinkle')
    spike.calibrate()
    print('test')
    try:
        await point_note('D')
        await asyncio.sleep(1)
        await point_note('C')
        await asyncio.sleep(1)
        await point_note('E')
        await asyncio.sleep(1)
    except Exception as e:
        logger.exception(e)

try:
    loop = asyncio.get_event_loop()
    loop.create_task(async_main())
    loop.create_task(tune_change())
    for signo in [signal.SIGINT, signal.SIGTERM]:
        func = functools.partial(asyncio.ensure_future, signal_handler(signo, loop))
        loop.add_signal_handler(signo, func)

    sys.exit(loop.run_forever())
    #loop.close()
except KeyboardInterrupt:
    del player
    pygame.midi.quit()
    logger.debug('End of program')
