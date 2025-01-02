import asyncio
import aiohttp
from .usbserial import UsbserialApi
from aiohttp.web import Request
from aiohttp.web import Response
from ....htserver import exposed_http
from ....htserver import make_json_response
from serial import SerialException, SerialTimeoutException


class UsbApi:
    def __init__(self, usb_serial_api=None) -> None:
        self.usb_serial_api = usb_serial_api or UsbserialApi()  # Create a new instance if none is passed

    async def send_serial_command(self, command):
        """Send a command to the serial API and return the response."""
        try:
            await self.usb_serial_api.init_serial_connection()
            if not self.usb_serial_api.serial_reader or not self.usb_serial_api.serial_writer:
                return {"error": "Failed to open serial connection"}

            # Write the command to the serial port
            await self.usb_serial_api.serial_write(command)
            await asyncio.sleep(10)  # Wait for the command to be processed

            async with self.usb_serial_api.lock:
                response = self.usb_serial_api.response_data.strip()
                self.usb_serial_api.response_data = ""  # Clear for the next command

            if not response:
                return {"error": "No response from serial device"}

            return {"message": "Command processed successfully", "response": response}

        except (SerialException) as e:
            return {"error": f"Serial communication error: {str(e)}"}

        finally:
            # Close the connection if open
            if self.usb_serial_api.serial_writer:
                self.usb_serial_api.serial_writer.close()

    async def enumerate_usb_device(self, os, location):
        """Enumerate USB devices based on OS over serial"""
        if location == 'host':
            return {"error": "Device enumeration on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wmic path Win32_USBControllerDevice get Dependent'
        elif os == 'linux':
            command = "lsusb"
        elif os == 'edk':
            command = "dh -p usbio >a fs0:log.txt"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def usb_driver_information(self, os, location):
        """Retrieve USB device information filtered by description (e.g., '%USB%') over serial"""
        if location == 'host':
            return {"error": "USB description filter on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic path Win32_PnPSignedDriver where 'DeviceName like '%USB%'' get DeviceName,DriverVersion"
        elif os == 'linux':
            command = "lsusb | grep 'USB'"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def check_usb_device_info(self, os, location):
        """Check USB driver information over serial"""
        if location == 'host':
            return {"error": "Driver info check on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wmic path CIM_LogicalDevice where "Description like \'%USB%\'" get DeviceID, Description'
        elif os == 'linux':
            command = "lsusb -v"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def usb_error_handling(self, os, location):
        """Detect and handle USB errors over serial"""
        if location == 'host':
            return {"error": "Error handling on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wevtutil qe System /q:"*[System[Provider[@Name=\'Microsoft-Windows-USB-USBXHCI\']]]" /f:text'  # USB-related Event ID
        elif os == 'linux':
            command = "dmesg | grep -i usb"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def usb_power_management(self, os, location):
        """Check USB power management over serial"""
        if location == 'host':
            return {"error": "Power management on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'powercfg -devicequery wake_armed'
        elif os == 'linux':
            command = "lsusb -v | grep -i power"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    @exposed_http('GET', '/enumerate_usb_device')

    async def enumerate_usb_device(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.enumerate_usb_device(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/usb_description_filter')

    async def usb_driver_information(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.usb_driver_information(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/check_usb_driver_info')

    async def check_usb_device_info(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.check_usb_device_info(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/usb_error_handling')

    async def usb_error_handling(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.usb_error_handling(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/usb_power_management')

    async def usb_power_management(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.usb_power_management(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    # Helper to get parameters
    async def get_params(self, request: Request) -> Response:
        location = request.rel_url.query.get('location', 'target')
        os = request.rel_url.query.get('os', 'windows').lower()
        if location not in ['host', 'target']:
            location = 'target'
        if os not in ['windows', 'linux', 'edk']:
            os = 'windows'
        return os, location
