import asyncio
import aiohttp
from .usbserial import UsbserialApi
from aiohttp.web import Request
from aiohttp.web import Response
from ....htserver import exposed_http
from ....htserver import make_json_response
from serial import SerialException, SerialTimeoutException

class BluetoothApi:
    def __init__(self, usb_serial_api=None) -> None:
        self.usb_serial_api = usb_serial_api or UsbserialApi()  # Assuming UsbserialApi can handle Bluetooth as well

    async def send_serial_command(self, command):
        """Send a command to the serial API and return the response."""
        try:
            await self.usb_serial_api.init_serial_connection()
            if not self.usb_serial_api.serial_reader or not self.usb_serial_api.serial_writer:
                return {"error": "Failed to open serial connection"}

            # Write the command to the serial port
            await self.usb_serial_api.serial_write(command)
            await asyncio.sleep(10)

            async with self.usb_serial_api.lock:
                response = self.usb_serial_api.response_data.strip()
                self.usb_serial_api.response_data = ""  # Clear for the next command

            if not response:
                return {"error": "No response from serial device"}

            return {"message": "Command processed successfully", "response": response}

        except SerialException as e:
            return {"error": f"Serial communication error: {str(e)}"}

        finally:
            if self.usb_serial_api.serial_writer:
                self.usb_serial_api.serial_writer.close()

    async def enumerate_bluetooth_device_logic(self, os, location):
        """Enumerate Bluetooth devices based on OS over serial"""
        if location == 'host':
            return {"error": "Device enumeration on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wmic path Win32_PnPEntity where "Description like \'%Bluetooth%\'" get Name,DeviceID'
        elif os == 'linux':
            command = "lspci | grep -i bluetooth"
        elif os == 'edk':
            command = "dh -p usbio >a fs0:log.txt"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def bluetooth_driver_information_logic(self, os, location):
        """Retrieve Bluetooth driver information over serial"""
        if location == 'host':
            return {"error": "Driver info retrieval on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wmic path Win32_PnPSignedDriver where "DeviceName like \'%Bluetooth%\'" get DeviceName,DriverVersion'
        elif os == 'linux':
            command = "dmesg | grep -i bluetooth"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def check_bluetooth_status_logic(self, os, location):
        """Check Bluetooth status over serial"""
        if location == 'host':
            return {"error": "Bluetooth status check on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wmic service where "Name=\'bthserv\'" get State'
        elif os == 'linux':
            command = "lsmod | grep bluetooth"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def bluetooth_error_handling_logic(self, os, location):
        """Detect and handle Bluetooth errors over serial"""
        if location == 'host':
            return {"error": "Error handling on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wevtutil qe System /q:"*[System[Provider[@Name=\'Microsoft-Windows-BTHUSB\']]]" /f:text'
        elif os == 'linux':
            command = "dmesg | grep -i bluetooth"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def bluetooth_power_management_logic(self, os, location):
        """Check Bluetooth power management over serial"""
        if location == 'host':
            return {"error": "Power management on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wmic ntevent where "Logfile=\'System\' and SourceName=\'BTHUSB\'" get EventCode, Message'
        elif os == 'linux':
            command = "cat /proc/acpi/wakeup"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    @exposed_http('GET', '/enumerate_bluetooth_device')
    async def enumerate_bluetooth_device(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.enumerate_bluetooth_device_logic(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/bluetooth_driver_information')
    async def bluetooth_driver_information(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.bluetooth_driver_information_logic(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/check_bluetooth_status')
    async def check_bluetooth_status(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.check_bluetooth_status_logic(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/bluetooth_error_handling')
    async def bluetooth_error_handling(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.bluetooth_error_handling_logic(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/bluetooth_power_management')
    async def bluetooth_power_management(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.bluetooth_power_management_logic(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    async def get_params(self, request: Request) -> Response:
        location = request.rel_url.query.get('location', 'target')
        os = request.rel_url.query.get('os', 'windows').lower()
        if location not in ['host', 'target']:
            location = 'target'
        if os not in ['windows', 'linux', 'edk']:
            os = 'windows'
        return os, location
