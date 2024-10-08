import os
import sys
import serial
import serial.serialutil
import crcmod
import math

#battery_voltage = 11400
    
global port
""""
header<5 byte - string>:<'start'>
version<2 byte>:<0x01>
src<3 byte - string>:<'RPI'>
dst<6 byte - string>:<'RP2040'>
unique tag command <2 byte>
len <2 byte>:
value<numerical value>:
trailer<2 byte + 3 byte - string>:<0xcrc><'end'>
sta:1,FF:4:0010,DA21\n
"""


def header():
    headervalue = f"{'sta'}:{'2'}"
    return headervalue

def payload(tag, value):
    #hexvalue = hex(value)  
    return f"{tag}:{len(value)}:{value}"

def calculate_percentage(percentage):
    # Maximum capacity in hexadecimal
    max_capacity_hex = 0x2303

    # Convert to decimal
    max_capacity_dec = int(max_capacity_hex)

    # Create an array to store the capacities in hexadecimal
    hex_capacities = []

    # Calculate and store the hexadecimal values for each percentage from 0% to 100%
    #for percent in range(101):
    capacity_dec = round(max_capacity_dec * (percentage / 100))
    capacity_hex = f"{capacity_dec:04x}"
    return capacity_hex
    #hex_capacities.append(capacity_hex)

# Function to get capacity values based on percentage
#def get_capacity_by_percentage(percentage):
#    if 0 <= percentage <= 100:
#        return hex_capacities[percentage]
#    else:
#        raise ValueError("Percentage must be between 0 and 100.")

# Prompt user for a percentage input and display the corresponding hexadecimal value
#try:
#    percentage = int(input("Enter a percentage (0-100): "))
#    capacity_hex = get_capacity_by_percentage(percentage)
#    print(f"{percentage}%: {capacity_hex}")
#except ValueError as e:
#    print(e)
#    return math.trunc(battery_voltage * (percentage / 100))

class ProtocolFrame:
    def __init__(self, header, payload):
        self.header = header
        self.payload = payload


    def encode(self):
        # Concatenate header, payload, and trailer
        # Calculate CRC for the payload
        crc = self.calculate_crc()
        # Create trailer with CRC
        trailer = f"{crc:04X}"  # Using 8 hex digits for CRC
        return f"{self.header},{self.payload},{trailer}"
        """
        if self.payload != None:
            # Calculate CRC for the payload
            crc = self.calculate_crc()
            # Create trailer with CRC
            trailer = f"{crc:04X}"  # Using 8 hex digits for CRC
            return f"{self.header},{self.payload},{trailer}"
        elif self.payload == None:
            return f"{self.header}"
        """

    @classmethod
    def decode(cls, frame_str):
        # Split frame into header, payload, and trailer
        header, payload, trailer = frame_str.split(',')

        # Extract CRC from trailer
        crc_str = trailer.split(':')[1]

        # Convert CRC string to integer
        crc = int(crc_str, 16)

        # Create ProtocolFrame instance
        frame = cls(header, payload)

        # Verify CRC
        if crc == frame.calculate_crc():
            return frame
        else:
            return None

    def calculate_crc(self):
        # select CRC-16-DNP
        crc16 = crcmod.mkCrcFun(0x13D65, 0xFFFF, True, 0xFFFF)
        #crc_func = crcmod.predefined.mkPredefinedCrcFun('crc-16')
        ###return crc_func(self.payload.encode())
        return crc16(self.payload.encode())

def taskWrite(data):
    if data != None:
        tx = prefix + data.encode('ascii') + b'\x0A'
    else:
        tx = prefix + b'\x0A'
    #data = tag+value+end
    #print("{} converting to ascii".format(data))
    #tx = data.encode('ascii')
    print("sending data {}\n".format(tx))
    #tx=data+"\r\n"+'\x00'
    port.flush()
    #print("port.flush\r\n")
    port.write(tx)
    #print("port.write data\r\n")
    #port.write(str.encode('\r\n','ascii'))
    #print("port. write newline\r\n")

def taskRead():
    data=''
    while True:
        try:
            if port.in_waiting > 0:
                #data=port.readline()
                data=port.read()
                print("{} got from RP2041\n".format(data.decode('ascii')))
                #if len(data) > 0:
                #    break
        except serial.serialutil.SerialException:
            break

def write(tag, value, propety):
    global port
    global prefix
    port = serial.Serial("/dev/ttyAMA3", baudrate=115200, timeout=2, xonxoff=False)

    #headerdata = header('RPI', 'RP2040')
    headerdata = None
    payloaddata = None

    print("battery tag {} value {} property {}".format(tag, value, propety));

    if tag != None and value != None and propety == "simulated":
        #headerdata = header('@','0x02',0)
        prefix = b'\x40' + b'\x02' + b'\x2C'
        headerdata = header()
        current_mah = calculate_percentage(value)
        print("value {} in percentage {}".format(value, current_mah))
        payloaddata = payload(tag, current_mah)
    elif tag == None and value == None and propety == "real-attach":
        prefix = b'\x40' + b'\x01'
        #headerdata = header('@','0x01',1)
    elif tag == None and value == None and propety == "simulated-attach":
        prefix = b'\x40' + b'\x04' 
        #headerdata = header('@','0x04',1)
    elif tag == None and value == None and propety == "detach":
        prefix = b'\x40' + b'\x03'
        #headerdata = header('@','0x03',1)

    if tag != None and value != None:
        frame = ProtocolFrame(headerdata, payloaddata)
        encoded_frame = frame.encode()
        #print("Encoded Frame:", encoded_frame)

        taskWrite(encoded_frame)
    else:
        taskWrite(None)
    #print("reading from single port /dev/ttyAMA3.....")
    #taskRead()
    port.close()


def read():
    global port
    port = serial.Serial("/dev/ttyAMA3", baudrate=115200, timeout=2, xonxoff=False)
    #print("reading from port /dev/ttyAMA3.....")
    #taskRead();
    port.close()



