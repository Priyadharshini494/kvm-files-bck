import re
import os
import stat
import functools
import struct
import serial
import asyncio
import subprocess
from aiohttp.web import Request, Response
from ....htserver import exposed_http, make_json_response
from ....logging import get_logger
from aiohttp import web
import threading
from serial import SerialException, SerialTimeoutException
import time

# Serial communication settings
SERIAL_PORT = '/dev/ttyGS0'  # Adjust according to your setup
BAUD_RATE = 115200
READ_TIMEOUT = 1
COMMAND_TIMEOUT = 5  # seconds
MAX_WAIT_COUNT = 1000    # number of times to wait for heartbeat before restarting
DEFAULT_COMMAND = 'reset -c >a fs0:log.txt'

# Global variables for serial connection and task management
serial_conn = None
read_task = None
write_task = None
response_data = ""
lock = threading.Lock()

class ResetEdkApi:
    def __init__(self) -> None:
        pass

    async def init_serial_connection(self):
        global serial_conn
        try:
            # Initialize serial connection
            serial_conn = serial.Serial(port=SERIAL_PORT, baudrate=BAUD_RATE, timeout=READ_TIMEOUT)
            print("Serial port initialized.")
        except SerialException as e:
            print(f"Failed to initialize serial port: {e}")
            serial_conn = None

    def serial_read(self):
        global response_data
        wait_count = 0
        while serial_conn and serial_conn.is_open:
            try:
                if serial_conn.in_waiting:
                    data = serial_conn.read(serial_conn.in_waiting).decode('utf-8', errors='ignore')
                    with lock:
                        response_data += data
                    print(f"Received from serial: {data.strip()}")
                    # Reset wait count if valid data received
                    if "Heartbeat" in data:
                        wait_count = 0

                time.sleep(1)

                # Check if we've waited too long for a heartbeat
                if wait_count >= MAX_WAIT_COUNT:
                    print("Target is not ready.")
                    raise IOError("Exceeded maximum wait count for heartbeat.")
                
                wait_count += 1

            except IOError as e:
                print(f"OS error in heartbeat thread: {e}")
                print("Resetting serial port due to prolonged wait...")
                serial_conn.close()
                time.sleep(1)
                serial_conn.open()
                wait_count = 0  # reset wait count after reopening serial port

                print("Serial port reopened successfully")
            except (SerialException, SerialTimeoutException) as e:
                print(f"Error during serial read: {e}")
                break
            except Exception as e:
                print(f"Unexpected error during serial read: {e}")
                break

    def serial_write(self, command):
        try:
            if serial_conn and serial_conn.is_open:
                serial_conn.write(command.encode('utf-8'))
                print(f"Command sent: {command}")
            else:
                print("Serial connection is not open.")
        except (SerialException, SerialTimeoutException) as e:
            print(f"Error during serial write: {e}")
        except Exception as e:
            print(f"Unexpected error during serial write: {e}")

    async def handle_serial_request(self, request):
        global read_task, write_task, response_data

        command = DEFAULT_COMMAND

        # Initialize serial connection if not already done
        if serial_conn is None or not serial_conn.is_open:
            await self.init_serial_connection()
            if serial_conn is None or not serial_conn.is_open:
                return make_json_response({"error": "Failed to open serial connection"}, status=500)

        # Start read and write tasks
        response_data = ""
        write_task = threading.Thread(target=self.serial_write, args=(command,))
        read_task = threading.Thread(target=self.serial_read)

        write_task.start()
        read_task.start()

        # Wait for command to be processed
        await asyncio.sleep(COMMAND_TIMEOUT)  # Adjust sleep as necessary for processing time

        # Ensure proper shutdown
        if serial_conn and serial_conn.is_open:
            serial_conn.close()

        # Wait for tasks to complete
        write_task.join()
        read_task.join()

        with lock:
            response = response_data.strip()
        
        if not response:
            return make_json_response({"error": "No response from serial device"}, status=500)

        return make_json_response({"message": "Command processed successfully", "response": response})
        
    async def cleanup(self, app):
        global serial_conn
        if serial_conn and serial_conn.is_open:
            serial_conn.close()

    @exposed_http('POST', '/reset-edk')
    async def reset_edk(self, request: Request) -> Response:
        try:
            response_data, status = await self.handle_serial_request(request)
            return make_json_response({"message": response_data}, status=status)

        except Exception as e:
            get_logger(0).info(f"Request processing error: {str(e)}")
            return make_json_response({"error": "An error occurred processing the request."}, status=500)
