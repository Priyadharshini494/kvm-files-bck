import asyncio
from .usbserial import UsbserialApi
from aiohttp.web import Request, Response
from ....htserver import exposed_http, make_json_response
from serial import SerialException

class WiFiApi:
    def __init__(self, usb_serial_api=None) -> None:
        self.usb_serial_api = usb_serial_api or UsbserialApi()

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

    # Retrieve WiFi Adapter Information
    async def wifi_adapter_information_logic(self, os, location):
        """Retrieve WiFi adapter information over serial"""
        if location == 'host':
            return {"error": "WiFi adapter information on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic path Win32_NetworkAdapter where \"NetConnectionID='Wi-Fi'\" get Name,Manufacturer,NetConnectionID,Speed,MACAddress"
        elif os == 'linux':
            command = "ifconfig -a"  # For WiFi adapter information in Linux
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Retrieve WiFi Adapter Driver Information
    async def wifi_adapter_driver_info_logic(self, os, location):
        """Retrieve WiFi driver information over serial"""
        if location == 'host':
            return {"error": "Driver info retrieval on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic path Win32_PnPSignedDriver where \"DeviceName like '%Wi-Fi%'\" get DeviceName,DriverVersion,Manufacturer,DriverDate"
        elif os == 'linux':
            command = "ethtool -i wlan0"  # For driver information in Linux
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Check WiFi Adapter Status
    async def wifi_adapter_status_logic(self, os, location):
        """Check WiFi adapter status over serial"""
        if location == 'host':
            return {"error": "WiFi status check on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic nic where \"NetConnectionID='Wi-Fi'\" get NetConnectionStatus,Name"
        elif os == 'linux':
            command = "ip link show"  # WiFi status check in Linux
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Check WiFi Adapter IP Configuration
    async def wifi_ip_configuration_logic(self, os, location):
        """Retrieve WiFi adapter IP configuration over serial"""
        if location == 'host':
            return {"error": "IP configuration on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic path Win32_NetworkAdapterConfiguration where \"Description like '%Wi-Fi%'\" get Description,IPAddress,IPSubnet,DefaultIPGateway"
        elif os == 'linux':
            command = "ifconfig wlan0"  # For IP configuration in Linux
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Retrieve WiFi Power Management Information
    async def wifi_power_management_logic(self, os, location):
        """Retrieve WiFi power management information over serial"""
        if location == 'host':
            return {"error": "Power management on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic path Win32_NetworkAdapter where \"NetConnectionID='Wi-Fi'\" get PowerManagementSupported,PowerManagementCapabilities"
        elif os == 'linux':
            command = "cat /proc/acpi/wakeup"  # For power management in Linux
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Retrieve WiFi Adapter MAC Address
    async def wifi_mac_address_logic(self, os, location):
        """Retrieve WiFi MAC address over serial"""
        if location == 'host':
            return {"error": "MAC address retrieval on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic nic where \"NetConnectionID='Wi-Fi'\" get MACAddress"
        elif os == 'linux':
            command = "cat /sys/class/net/wlan0/address"  # For MAC address in Linux
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Exposed Endpoints
    @exposed_http('GET', '/wifi_adapter_information')
    async def wifi_adapter_information(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.wifi_adapter_information_logic(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/wifi_adapter_driver_info')
    async def wifi_adapter_driver_info(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.wifi_adapter_driver_info_logic(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/wifi_adapter_status')
    async def wifi_adapter_status(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.wifi_adapter_status_logic(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/wifi_ip_configuration')
    async def wifi_ip_configuration(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.wifi_ip_configuration_logic(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/wifi_power_management')
    async def wifi_power_management(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.wifi_power_management_logic(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/wifi_mac_address')
    async def wifi_mac_address(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.wifi_mac_address_logic(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    # Utility function to get parameters
    async def get_params(self, request: Request) -> Response:
        location = request.rel_url.query.get('location', 'target')
        os = request.rel_url.query.get('os', 'windows').lower()
        if location not in ['host', 'target']:
            location = 'target'
        if os not in ['windows', 'linux']:
            os = 'windows'
        return os, location
