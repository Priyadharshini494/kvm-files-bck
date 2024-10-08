import asyncio
import aiohttp
from .usbserial import UsbserialApi
from aiohttp.web import Request
from aiohttp.web import Response
from ....htserver import exposed_http
from ....htserver import make_json_response
from serial import SerialException, SerialTimeoutException

# PCIe API class
# class PciApi:
#     def __init__(self, usb_serial_api=None) -> None:
#         if usb_serial_api is not None:
#             self.usb_serial_api = UsbserialApi()
class PciApi:
    def __init__(self, usb_serial_api=None) -> None:
        self.usb_serial_api = usb_serial_api or UsbserialApi() # Create a new instance if none is passed
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

    async def enumerate_device(self, os, location):
        """Enumerate PCI devices based on OS over serial"""
        if location == 'host':
            return {"error": "Device enumeration on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wmic path Win32_PnPEntity get Name,DeviceID'
        elif os == 'linux':
            command = "lspci"
        elif os == 'edk':
            command = "pci >a fs0:log.txt"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def pci_description_filter(self, os, location):
        """Retrieve PCI device information filtered by description (e.g., '%PCI%') over serial"""
        if location == 'host':
            return {"error": "PCI description filter on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wmic path Win32_PnPEntity where "Description like \'%PCI%\'" get Name,DeviceID,Description'
        elif os == 'linux':
            command = "lspci | grep 'PCI'"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def check_driver_info(self, os, location):
        """Check driver information over serial"""
        if location == 'host':
            return {"error": "Driver info check on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wmic path Win32_PNPSignedDriver get DeviceName,DriverVersion'
        elif os == 'linux':
            command = "lspci -k"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def error_handling(self, os, location):
        """Detect and handle PCIe errors over serial"""
        if location == 'host':
            return {"error": "Error handling on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wevtutil qe System /q:"*[System[(EventID=2)]]" /f:text'
        elif os == 'linux':
            command = "dmesg | grep -i pcie"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def power_management(self, os, location):
        """Check PCIe power management over serial"""
        if location == 'host':
            return {"error": "Power management on host is not supported."}

        command = ""
        if os == 'windows':
            command = "powercfg -devicequery wake_armed"
        elif os == 'linux':
            command = "lspci -vvv | grep PME"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def memory_info(self, os, location):
        """Retrieve memory information over serial"""
        if location == 'host':
            return {"error": "Memory info on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wmic memorychip get capacity,manufacturer,serialnumber'
        elif os == 'linux':
            command = "dmidecode -t memory"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def baseboard_info(self, os, location):
        """Retrieve baseboard (motherboard) information over serial"""
        if location == 'host':
            return {"error": "Baseboard info on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wmic baseboard get product,manufacturer,serialnumber'
        elif os == 'linux':
            command = "dmidecode -t baseboard"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def check_configuration_space(self, os, location):
        """Retrieve the configuration space of Bus 0, Device 0, Function 0"""
        if location == 'host':
            return {"error": "Operation not supported in host"}

        command = ""
        if os == 'edk':
            command = 'pci 00 00 00 -i >a fs0:log.txt'
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    async def check_configuration_space_segment(self, os, location):
        """Retrieve the configuration space of Segment 0, Bus 0, Device 0, Function 0"""
        if location == 'host':
            return {"error": "Operation not supported in host"}

        command = ""
        if os == 'edk':
            command = 'pci 00 00 00 -s 0 >a fs0:log.txt'
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)


    @exposed_http('GET' , '/pci_enumerate_device')

    async def enumerate_device1(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.enumerate_device(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET' , '/pci_description_filter')

    async def pci_description_filter1(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.pci_description_filter(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/pci_check_driver_info')

    async def check_driver_info1(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.check_driver_info(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/pci_error_handling')

    async def error_handling1(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.error_handling(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/pci_power_management')
    async def power_management1(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.power_management(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/pci_memory_info')

    async def memory_info1(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.memory_info(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/pci_baseboard_info')

    async def baseboard_info1(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.baseboard_info(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/pci_check_configuration_space')

    async def check_configuration_space1(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.check_configuration_space(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET','/pci_check_configuration_space_segment')

    async def check_configuration_space_segment1(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.check_configuration_space_segment(os, location)
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
