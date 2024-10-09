import asyncio
from aiohttp import web
import serial
import threading
from serial import SerialException, SerialTimeoutException
import time
from aiohttp.web import Request
from aiohttp.web import Response
from ....htserver import exposed_http
from ....htserver import exposed_ws
from ....htserver import make_json_response
from ....htserver import WsSession
from ....logging import get_logger
from ....validators import raise_error

# Serial communication settings
SERIAL_PORT = '/dev/ttyGS0'  # Adjust according to your setup
BAUD_RATE = 115200
READ_TIMEOUT = 1
COMMAND_TIMEOUT = 5  # seconds
MAX_WAIT_COUNT = 1000    # number of times to wait for heartbeat before restarting
DEFAULT_COMMAND = 'bcfg boot mv {order} 0 >a fs0:log.txt'

# Global variables for serial connection and task management
serial_conn = None
read_task = None
write_task = None
response_data = ""
lock = threading.Lock()
class FlashosApi:
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
            # else:
            #     print("Waiting for data...")

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

    def serial_write(self,command):
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

    @exposed_http('POST', '/flash-os')

    async def handle_serial_request(self, request: Request) -> Response:

        global read_task, write_task, response_data
        try:
            data = await request.json()
            command = DEFAULT_COMMAND;
            order = data.get('order', '')
            if not order:
                return make_json_response({"error": "No order provided"}, status=400)
        except Exception as e:
            return make_json_response({"error": f"Invalid JSON input: {e}"}, status=400)

        command = DEFAULT_COMMAND.format(order=order)

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
        
        
        return make_json_response({"message": "Command processed success"})

