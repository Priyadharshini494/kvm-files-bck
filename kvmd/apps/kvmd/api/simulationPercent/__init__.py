import os
import sys
import serial
import serial.serialutil
import crcmod

from .....logging import get_logger
    
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
"""

def header(src, dst):
    return f"{'start'}:{0x01}:{src}:{dst}"

def payload(tag, value):
    return f"{tag}:{len(value)}:{value}"

class ProtocolFrame:
    def __init__(self, header, payload):
        self.header = header
        self.payload = payload

    def encode(self):
        # Calculate CRC for the payload
        crc = self.calculate_crc()

        # Create trailer with CRC
        trailer = f"CRC:{crc:04X}{':end'}"  # Using 8 hex digits for CRC

        # Concatenate header, payload, and trailer
        return f"{self.header},{self.payload},{trailer}"

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
    logger = get_logger(0)
    port.flush()
    logger.info("port.flush\r\n")
    port.write(str.encode(data,'ascii'))
    logger.info("port.write data\r\n")
    port.write(str.encode('\r\n','ascii'))
    logger.info("port. write newline\r\n")

def write(tag, value):
    logger = get_logger(0)
    global port
    port = serial.Serial("/dev/ttyAMA0", baudrate=115200, timeout=2, xonxoff=False)
    logger.info("{}.{} tag, value".format(tag, value))

    headerdata = header('RPI', 'USBUart')

    payloaddata = payload(tag, str(value))
    frame = ProtocolFrame(headerdata, payloaddata)
    encoded_frame = frame.encode()
    logger.info("Encoded Frame:" + str(encoded_frame))

    taskWrite(encoded_frame)

    port.close()

