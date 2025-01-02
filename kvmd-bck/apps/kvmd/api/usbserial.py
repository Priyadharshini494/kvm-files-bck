import asyncio
import serial
from aiohttp import web
import serial_asyncio
from aiohttp.web import Request, Response
from ....htserver import exposed_http, make_json_response
from serial import SerialException, SerialTimeoutException
from ....logging import get_logger

SERIAL_PORT = '/dev/ttyGS0'  # Adjust according to your setup
BAUD_RATE = 115200
COMMAND_TIMEOUT = 5  # seconds
MAX_WAIT_COUNT = 1000  # number of times to wait for heartbeat before restarting

class UsbserialApi:
    def __init__(self) -> None:
        self.serial_reader = None
        self.serial_writer = None
        self.response_data = ""
        self.lock = asyncio.Lock()
        self.should_read = True  # Flag to control reading

    async def init_serial_connection(self):
        """Initialize the serial connection asynchronously."""
        try:
            self.serial_reader, self.serial_writer = await serial_asyncio.open_serial_connection(
                url=SERIAL_PORT, baudrate=BAUD_RATE
            )
            print("Serial connection initialized.")
        except SerialException as e:
            print(f"Failed to initialize serial connection: {e}")
            self.serial_reader, self.serial_writer = None, None

    async def close_serial_connection(self):
        """Clean up and close the serial connection."""
        if self.serial_writer:
            self.serial_writer.close()
            await self.serial_writer.wait_closed()
            self.serial_writer = None
        if self.serial_reader:
            self.serial_reader = None
        print("Serial connection closed.")

    async def serial_read(self):
        """Asynchronously read data from the serial connection."""
        wait_count = 0

        try:
            while self.should_read and self.serial_writer:  # Check the reading flag and writer existence
                if self.serial_reader:
                    data = await self.serial_reader.read(1024)  # Read asynchronously
                    if data:
                        decoded_data = data.decode('utf-8', errors='ignore')
                        async with self.lock:
                            self.response_data += decoded_data
                        print(f"Received from serial: {decoded_data.strip()}")
                        wait_count = 0  # Reset wait count on valid data
                    else:
                        print("Waiting for data...")
                else:
                    print("Serial reader not initialized.")
                    break  # Exit the loop if serial reader is not initialized

                await asyncio.sleep(1)  # Non-blocking sleep

                # Check if we've waited too long for a heartbeat
                if wait_count >= MAX_WAIT_COUNT:
                    print("Target is not ready.")
                    raise IOError("Exceeded maximum wait count for heartbeat.")

                wait_count += 1

        except (SerialException, SerialTimeoutException) as e:
            print(f"Error during serial read: {e}")
            await self.close_serial_connection()  # Close the connection on error
        except Exception as e:
            print(f"Unexpected error during serial read: {e}")
            await self.close_serial_connection()  # Handle any other exceptions

    async def serial_write(self, command):
        """Asynchronously write data to the serial connection."""
        try:
            if self.serial_writer:
                self.serial_writer.write(command.encode("utf-8"))
                await self.serial_writer.drain()
                print(f"Command sent: {command}")

                # Start reading after writing
                self.should_read = True
                asyncio.create_task(self.serial_read())  # Run serial_read in the background
        except SerialException as e:
            print(f"Serial write error: {e}")
            await self.close_serial_connection()  # Close the connection on error
        except Exception as e:
            print(f"Unexpected error during serial write: {e}")
            await self.close_serial_connection()  # Handle any other exceptions

    @exposed_http("POST", "/serial")
    async def handle_serial_request(self, request: Request) -> Response:
        """Handle HTTP request to communicate with the serial device."""
        data = await request.json()
        cmd = data.get("cmd", "")

        if not cmd:
            return make_json_response({"error": "No command provided"}, status=400)

        # Initialize serial connection if not already done
        if not self.serial_reader or not self.serial_writer:
            await self.init_serial_connection()
            if not self.serial_reader or not self.serial_writer:
                return make_json_response({"error": "Failed to open serial connection"}, status=500)

        # Write the command
        await self.serial_write(cmd)

        # Allow the command to process and gather response
        await asyncio.sleep(COMMAND_TIMEOUT)

        # Stop reading after the command has been processed
        self.should_read = False

        async with self.lock:
            response = self.response_data.strip()
            self.response_data = ""

        # Cleanup the serial connection after handling the command
        await self.close_serial_connection()

        if not response:
            return make_json_response({"error": "No response from serial device"}, status=500)

        return make_json_response({"message": "Command processed successfully", "response": response})

