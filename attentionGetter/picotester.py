import bluetooth
import time
from machine import Pin
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
    ble.gap_advertise(200_000, payload)
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


while True:
    print("Current mode:", current_mode)
    time.sleep(1)

    time.sleep_ms(20)
