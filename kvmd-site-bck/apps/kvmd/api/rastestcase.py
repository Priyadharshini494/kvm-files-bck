import asyncio
from .usbserial import UsbserialApi
from aiohttp.web import Request, Response
from ....htserver import exposed_http, make_json_response
from serial import SerialException

class RasApi:
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

    # CPU Load and Status
    async def check_cpu_status_logic(self, os, location):
        if location == 'host':
            return {"error": "CPU status check on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic cpu get LoadPercentage, Name, Status"
        elif os == 'linux':
            command = "top -bn1 | grep 'Cpu(s)'"
        elif os == 'edk':
            command = "smbiosview -t 4 >a fs0:log.txt"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Fan Status
    async def check_fan_status_logic(self, os, location):
        if location == 'host':
            return {"error": "Fan status check on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic path Win32_Fan get Name, DesiredSpeed, Status"
        elif os == 'linux':
            command = "dmesg | grep -i fan"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Memory Information
    async def check_memory_info_logic(self, os, location):
        if location == 'host':
            return {"error": "Memory info check on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic memorychip get BankLabel, Capacity, Speed, Status"
        elif os == 'linux':
            command = "free -m"
        elif os == 'edk':
            command = "dmem"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Disk Drive Status
    async def check_disk_status_logic(self, os, location):
        if location == 'host':
            return {"error": "Disk status check on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic diskdrive get Status, Model, Size, MediaType"
        elif os == 'linux':
            command = "lsblk -o NAME,SIZE,TYPE,MODEL,STATE"
        elif os == 'edk':
            command = "dh -p diskio >a fs0:log.txt"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Network Interface Status
    async def check_network_status_logic(self, os, location, interface):
        if location == 'host':
            return {"error": "Network status check on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic nic get Name, NetConnectionStatus"
        elif os == 'linux':
            command = "ip link show"
        elif os == 'edk':
            command = f"ifconfig -l {interface} >a fs0:log.txt"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Battery Status
    async def check_battery_status_logic(self, os, location):
        if location == 'host':
            return {"error": "Battery status check on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic path Win32_Battery get BatteryStatus, EstimatedChargeRemaining, EstimatedRunTime"
        elif os == 'linux':
            command = "upower -i /org/freedesktop/UPower/devices/battery_BAT0"
        elif os == 'edk':
            command = "smbiosview -t 22 >a fs0:log.txt"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # System Events
    async def check_system_events_logic(self, os, location):
        if location == 'host':
            return {"error": "Event check on host is not supported."}

        command = ""
        if os == 'windows':
            command = 'wevtutil qe System /c:5 /f:text /q:"*[System[(EventID=41) or (EventID=6008)]]"'
        elif os == 'linux':
            command = "journalctl -n 5 -p 0..4"
        elif os == 'edk':
            command = "smbiosview -t 15 >a fs0:log.txt"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Exposed Endpoints
    @exposed_http('GET', '/check_cpu_status')
    async def check_cpu_status(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        result = await self.check_cpu_status_logic(os, location)
        return make_json_response(result)

    @exposed_http('GET', '/check_fan_status')
    async def check_fan_status(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        result = await self.check_fan_status_logic(os, location)
        return make_json_response(result)

    @exposed_http('GET', '/check_memory_info')
    async def check_memory_info(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        result = await self.check_memory_info_logic(os, location)
        return make_json_response(result)

    @exposed_http('GET', '/check_disk_status')
    async def check_disk_status(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        result = await self.check_disk_status_logic(os, location)
        return make_json_response(result)

    @exposed_http('GET', '/check_network_status')
    async def check_network_status(self, request: Request) -> Response:
        interface = request.rel_url.query.get('interface', 'enp1s0')
        os, location = await self.get_params(request)
        result = await self.check_network_status_logic(os, location, interface)
        return make_json_response(result)

    @exposed_http('GET', '/check_battery_status')
    async def check_battery_status(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        result = await self.check_battery_status_logic(os, location)
        return make_json_response(result)

    @exposed_http('GET', '/check_system_events')
    async def check_system_events(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        result = await self.check_system_events_logic(os, location)
        return make_json_response(result)

    # Utility function to get parameters
    async def get_params(self, request: Request) -> tuple:
        location = request.rel_url.query.get('location', 'target')
        os = request.rel_url.query.get('os', 'windows').lower()
        return os if os in ['windows', 'linux', 'edk'] else 'windows', location
