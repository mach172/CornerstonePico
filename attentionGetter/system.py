import bluetooth
import time
from machine import Pin, SPI
from micropython import const

#defines bluetooth events
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

#defines bluetooth service and command UUIDs
SERVICE_UUID = bluetooth.UUID("74fc1f14-5f97-46a9-992b-70173d569dca")
COMMAND_UUID = bluetooth.UUID("0227db08-d979-4305-8ddb-4a0d030a29ad")

#current mode variable TODO inquire about 0-3
current_mode = 0 #0: green, 1: yellow, 2: red, 3: random bs

#initializes bluetooth and sets device name
ble = bluetooth.BLE()
ble.active(True)
ble.config(gap_name="Fridge Tracker Box")

#defines bluetooth service and command characteristics
COMMAND_SERVICE = (
    SERVICE_UUID,
    ((COMMAND_UUID, bluetooth.FLAG_WRITE),)
)

#registers bluetooth service and command characteristics
((command_handle,),) = ble.gatts_register_services((COMMAND_SERVICE,))

def advertise():
    name = b"Fridge Tracker Box"
    #advertising payload
    payload = (
        b"\x02\x01\x06"  # Flags
        + bytes((len(name) + 1, 0x09))  # Complete Local Name
        + name
    )

    #advertises device with payload and 1 second interval
    ble.gap_advertise(2_000_000, payload)
    print("Advertising as:", name.decode())

#handles bluetooth events
def on_ble_event(event, data):
    global current_mode

    #prints when central device connects
    if event == _IRQ_CENTRAL_CONNECT:
        print("Central connected")

    #prints when central device disconnects and restarts advertising
    elif event == _IRQ_CENTRAL_DISCONNECT:
        print("Central disconnected")
        advertise()

    #handles write events to the command characteristic
    elif event == _IRQ_GATTS_WRITE:
        #unpacks the data from the write event
        connection, attribute = data

        #checks if the write event is for the command characteristic
        if attribute == command_handle:
            #reads the data written to the command characteristic
            recieved = ble.gatts_read(command_handle)

            #checks if the received data is a single byte and if it is 0, 1, 2, or 3
            if len(recieved) == 1 and recieved[0] in (0, 1, 2, 3):
                current_mode = recieved[0]
                print("Mode changed to: ", current_mode)

#sets the bluetooth event handler
ble.irq(on_ble_event)

#advertises device
advertise()

#defines LED pins
greenLed = Pin(14, Pin.OUT, value=0)
yellowLed = Pin(15, Pin.OUT, value=0)
redLed = Pin(16, Pin.OUT, value=0)

#sets LED state based on current mode
def update_leds():
    if(current_mode == 0):
        greenLed.value(1)
        yellowLed.value(0)
        redLed.value(0)
    elif(current_mode == 1):
        greenLed.value(0)
        yellowLed.value(1)
        redLed.value(0)
    elif(current_mode == 2):
        greenLed.value(0)
        yellowLed.value(0)
        redLed.value(1)

def turn_off_leds():
    greenLed.value(0)
    yellowLed.value(0)
    redLed.value(0)


spi = SPI(
    0,
    baudrate=1000000,
    polarity=0,
    phase=0,
    sck=Pin(2),
    mosi=Pin(3),
    miso=Pin(4)
)

cs = Pin(1, Pin.OUT, value=1)

def read_register(register, count=1):
    cs.value(0)
    try:
        spi.write(bytearray([register | 0x80]))
        return spi.read(count, 0x00)
    finally:
        cs.value(1)

def write_register(register, value):
    cs.value(0)
    try:
        spi.write(bytearray([register & 0x7F, value]))
    finally:
        cs.value(1)

def select_bank(bank):
    write_register(0x7F, bank << 4)

select_bank(0)

sensor_id = read_register(0x00)[0]

if sensor_id != 0xEA:
    raise RuntimeError(
        "Failed to find sensor: " + hex(sensor_id)
    )

#sets gyroscope configuration to SPI
write_register(0x03, 0x10) 

#sets clock source to auto, turns off temp, sets circuitry to low power mode
write_register(0x06, 0x01)
time.sleep_ms(100)

#disables accelerometer and enables gyroscope 
write_register(0x07, 0x38)

#enables gyro DLPF and sets gyro scale to 500 dps
select_bank(2)
write_register(0x01, 0x03)
select_bank(0)

#converts 2 8-bit bytes to signed 16-bit integer
def signed16(high, low):
    value = (high << 8) | low
    if value >= 32768:
        value -= 65536
    return value

def read_gyro():
    data = read_register(0x33, 6)

    gx = signed16(data[0], data[1]) / 65.5
    gy = signed16(data[2], data[3]) / 65.5
    gz = signed16(data[4], data[5]) / 65.5

    return gx, gy, gz

print("Keep the device still to calibrate the gyroscope")

GYRO_AXIS = 1  #TODO adjust to correct axis (0: x, 1: y, 2: z)

total = 0.0

for i in range(200):
    total += read_gyro()[GYRO_AXIS]  # gyroscope y-axis
    time.sleep_ms(10)

gyro_bias = total / 200.0

print("Gyroscope calibrated. Bias:", gyro_bias)

OPEN_SPEED_THRESHOLD = 10  #TODO adjust degrees per second
OPEN_DIRECTION = 1  #TODO adjust based on orientation

while True:
    velocity = (
        read_gyro()[GYRO_AXIS] - gyro_bias
    ) * OPEN_DIRECTION

    if velocity > OPEN_SPEED_THRESHOLD:
        print("Door opened")

        update_leds()

        #TODO tune wait time
        time.sleep(20)

        turn_off_leds()

    time.sleep_ms(20)
