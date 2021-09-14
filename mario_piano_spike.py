import uasyncio as asyncio
import utime
import json
from hub import Image, display, button, port, motion, USB_VCP, BT_VCP

import hub_runtime
hub_runtime.system.reset()


com = BT_VCP(0)

light_port = port.F
light_port.mode(0)
while not light_port.device:
    utime.sleep_ms(10)
light = light_port.device
light.mode(3)

min_position = 0
max_position = -630

songs = ['stop', 'twinkle', 'shark', 'incy']
twinkle_imgs_old = [
    Image("00900:05950:99799:05950:00900"),
    Image("00903:05950:99799:05960:00900"),
    Image("00900:05950:99799:05950:00960"),
    Image("00900:08950:99799:05950:00900"),
    Image("00906:05950:99799:05950:70900"),
    Image("00900:05950:99799:05950:00900"),
    Image("00900:05950:99799:05950:00900"),
]
twinkle_imgs = [
    Image("00000:00500:05550:00500:00000"),
    Image("00000:00500:05850:00500:00000"),
    Image("00000:00800:08980:00800:00000"),
    Image("00000:04840:08980:04840:00000"),
    Image("00800:04940:89998:04940:00800"),
    Image("00400:04740:47774:04740:00400"),
    Image("00800:04940:89998:04940:00800"),
]

shark_imgs = [
    Image("00741:09991:98889:98889:09990"),
    Image("00753:09993:98889:98889:09990"),
    Image("00765:09995:98889:98889:09990"),
    Image("00653:09993:98889:98889:09990"),
    Image("00641:09991:98889:98889:09990"),
    Image("09990:98889:54445:98889:09990"),
    #Image("09990:98889:00000:98889:09990"),
    #Image("00643:09990:98889:98889:09990"),
    #Image("00643:09990:98889:98889:09990"),
]
incy_imgs = [
    Image("60006:60906:09990:60906:60006"),
    Image("60006:70907:09990:70907:60006"),
    Image("70007:80908:09990:80908:70007"),
    Image("70007:80908:09990:89098:70007"),
    Image("70007:80908:09990:80908:70007"),
    Image("70007:80908:09990:89098:70007"),
    Image("70007:80908:09990:80908:70007"),
    Image("70007:80908:09990:89098:70007"),
]

images = [
    #Image("07770:70007:79997:70007:07770"),
    #Image("00000:09090:99099:09090:00000"),
    Image.MUSIC_QUAVER,
    twinkle_imgs,
    #Image("90909:05950:99799:05950:90909"),
    #Image("00799:09990:79990:99990:99999"),
    shark_imgs,
    #Image("90009:91919:09990:90909:90009"),
    incy_imgs,
]

song = 0
display.show(images[song])


async def menu():
    global song
    button.left.was_pressed()
    while True:
        if button.left.was_pressed():
            if song > 0:
                song -= 1
            else:
                song = len(images) - 1
            display.show(images[song])
        elif button.right.was_pressed():
            if song < len(images) - 1:
                song += 1
            else:
                song = 0
            display.show(images[song])
        elif button.center.was_pressed():
            msg = {
                'cmd': 'teach',
                'song': songs[song],
                }
            #com.send(json.dumps(songs[song]).encode('utf-8'))
            com.send(json.dumps(msg).encode('utf-8'))

        #display.show(images[song])
        #await asyncio.sleep(0.1)

        if motion.gesture() == 1:
            msg = {
                'cmd': 'play',
                'song': songs[song]
                }
            com.send(json.dumps(msg).encode('utf-8'))
        await asyncio.sleep(0.1)


def motor(port, cmd):
    try:
        f = eval('port.{}.motor.{}'.format(port, cmd['action']))
        f(cmd['arg0'], **cmd['args'])
    except Exception as e:
        print(e)


async def calibrate(port='A'):
    global min_position, max_position
    m = eval('port.{}.motor'.format(port))
    m.mode(2)
    m.run_for_time(2000, speed=50)
    while m.busy(1):
        await asyncio.sleep_ms(10)
    m.run_for_degrees(20, speed=-20)
    while m.busy(1):
        await asyncio.sleep_ms(10)
    m.preset(0)
    #m.run_for_time(2000, speed=-50)
    #while m.busy(1):
    #    await asyncio.sleep_ms(10)
    #max_position = m.get()[0] + 20

async def to_position(position, port='A'):
    global max_position
    await unblink()
    m = eval('port.{}.motor'.format(port))
    _position = max_position / 7 * position
    #print(_position)
    m.run_to_position(_position, speed=100)
    while m.busy(1):
        await asyncio.sleep_ms(10)
    await blink()

async def shake(port='A'):
    await unblink()
    await asyncio.sleep_ms(100)
    await blink()
    #m = eval('port.{}.motor'.format(port))
    #m.run_for_degrees(5, speed=-100)
    #while m.busy(1):
    #    await asyncio.sleep_ms(10)
    #m.run_for_degrees(10, speed=100)
    #while m.busy(1):
    #    await asyncio.sleep_ms(10)
    #m.run_for_degrees(5, speed=-100)

async def blink():
    light.mode(3,b''+chr(2)+chr(2)+chr(0))
    #await asyncio.sleep_ms(100)
    #light.mode(3,b''+chr(0)+chr(0)+chr(0))

async def unblink():
    light.mode(3,b''+chr(0)+chr(0)+chr(0))


async def rpc():
    while True:
        if com.any():
            line = com.readline()
            rpc = json.loads(line)
            if rpc['cls'] == 'motor':
                motor(rpc['port'], rpc['cmd'])
            elif rpc['cls'] == 'calibrate':
                await calibrate()
            elif rpc['cls'] == 'to_position':
                await to_position(rpc['cmd']['position'])
            elif rpc['cls'] == 'shake':
                await shake()
        else:
            await asyncio.sleep_ms(10)


async def main():
    asyncio.create_task(rpc())
    asyncio.create_task(menu())
    while True:
        await asyncio.sleep(1)

def test():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        asyncio.new_event_loop()
        print()
        print('Finished')
        display.clear()


test()
