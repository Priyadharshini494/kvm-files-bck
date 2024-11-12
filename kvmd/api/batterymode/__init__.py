import os
import sys
import serial
import serial.serialutil
from .....logging import get_logger
def taskWrite(data):
    #tx=data.encode('ascii')
    logger = get_logger(0)
    logger.info("sending data {}\n".format(data))
    #tx=data+"\r\n"+'\x00'
    port.flush()
    #print("port.flush\r\n")
    port.write(data)
    #print("port.write data\r\n")
    #port.write(str.encode('\r\n','ascii'))
    #print("port. write newline\r\n")



def attach(attachbattery):
    global port
    port = serial.Serial("/dev/ttyAMA3", baudrate=115200, timeout=2, xonxoff=False)

    if attachbattery == "simulated":
        data=b'\x40' + b'\x01'
    elif attachbattery == "real":
        data=b'\x40' + b'\x02'
    #headerdata = header('RPI', 'RP2040')

    #payloaddata = payload(tag, str(value))
    #frame = ProtocolFrame(headerdata, payloaddata)
    #encoded_frame = frame.encode()
    #print("Encoded Frame:", encoded_frame)

    taskWrite(data)
    #print("reading from single port /dev/ttyAMA3.....")
    #taskRead()
    port.close()

