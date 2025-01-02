import asyncio
from .usbserial import UsbserialApi
from aiohttp.web import Request, Response
from ....htserver import exposed_http, make_json_response
from serial import SerialException

class SleepstateApi:
    def __init__(self, usb_serial_api=None) -> None:
        self.usb_serial_api = usb_serial_api or UsbserialApi()

    async def send_serial_command(self, command):
        """Send a command to the serial API and return the response."""
        try:
            await self.usb_serial_api.init_serial_connection()
            if not self.usb_serial_api.serial_reader or not self.usb_serial_api.serial_writer:
                return {"error": "Failed to open serial connection"}

            await self.usb_serial_api.serial_write(command)
            await asyncio.sleep(10)

            async with self.usb_serial_api.lock:
                response = self.usb_serial_api.response_data.strip()
                self.usb_serial_api.response_data = ""

            if not response:
                return {"error": "No response from serial device"}

            return {"message": "Command processed successfully", "response": response}

        except SerialException as e:
            return {"error": f"Serial communication error: {str(e)}"}

        finally:
            if self.usb_serial_api.serial_writer:
                self.usb_serial_api.serial_writer.close()

    # Sleep State Logic
    async def manage_sleep_state_logic(self, os, state, location):
        if location == 'host':
            return {"error": f"Managing sleep state '{state}' on host is not supported."}

        command = ""
        if os == 'windows':
            if state == 'S3':
                command = "rundll32.exe powrprof.dll,SetSuspendState Sleep"
            elif state == 'S4':
                command = "shutdown /h"
            elif state == 'S5':
                command = "shutdown /s /t 0"
            else:
                return {"error": "Invalid sleep state"}

        elif os == 'linux':
            if state == 'S3':
                command = "systemctl suspend"
            elif state == 'S4':
                command = "systemctl hibernate"
            elif state == 'S5':
                command = "systemctl poweroff"
            else:
                return {"error": "Invalid sleep state"}

        elif os == 'edk':
            if state == 'S3':
                command = "sleepstate 3 >a fs0:log.txt"
            elif state == 'S4':
                command = "sleepstate 4 >a fs0:log.txt"
            elif state == 'S5':
                command = "reset -s >a fs0:log.txt"
            else:
                return {"error": "Invalid sleep state"}

        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Exposed Endpoint for Sleep State Management
    @exposed_http('GET', '/manage_sleep_state')
    async def manage_sleep_state(self, request: Request) -> Response:
        os = request.rel_url.query.get('os', 'windows').lower()
        state = request.rel_url.query.get('state', 'S3').upper()
        location = request.rel_url.query.get('location', 'target')

        result = await self.manage_sleep_state_logic(os, state, location)
        return make_json_response(result)

    # Utility function to get parameters (if reused elsewhere)
    async def get_params(self, request: Request) -> tuple:
        location = request.rel_url.query.get('location', 'target')
        os = request.rel_url.query.get('os', 'windows').lower()
        return os if os in ['windows', 'linux', 'edk'] else 'windows', location
