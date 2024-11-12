import asyncio
from .usbserial import UsbserialApi
from aiohttp.web import Request, Response
from ....htserver import exposed_http, make_json_response
from serial import SerialException

class LanApi:
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

    # Retrieve LAN Adapter Information
    async def lan_adapter_information_logic(self, os, location, interface):
        """Retrieve LAN adapter information over serial"""
        if location == 'host':
            return {"error": "LAN adapter information on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic path Win32_NetworkAdapter where \"NetConnectionID='Ethernet'\" get Name,Manufacturer,NetConnectionID,Speed,MACAddress"
        elif os == 'linux':
            command = f"ethtool {interface}"  # For LAN adapter information in Linux
        elif os == 'edk':
            command = f"IfConfig -l {interface}"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Retrieve LAN Adapter Driver Information
    async def lan_adapter_driver_info_logic(self, os, location, interface):
        """Retrieve LAN driver information over serial"""
        if location == 'host':
            return {"error": "Driver info retrieval on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic path Win32_PnPSignedDriver where \"DeviceName like '%Ethernet%'\" get DeviceName,DriverVersion,Manufacturer,DriverDate"
        elif os == 'linux':
            command = f"ethtool -i {interface}"  # For driver information in Linux
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Check LAN Adapter Status
    async def lan_adapter_status_logic(self, os, location):
        """Check LAN adapter status over serial"""
        if location == 'host':
            return {"error": "LAN status check on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic nic where \"NetConnectionID='Ethernet'\" get NetConnectionStatus,Name"
        elif os == 'linux':
            command = "ip link show"  # LAN status check in Linux
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Check LAN Adapter IP Configuration
    async def lan_ip_configuration_logic(self, os, location, interface):
        """Retrieve LAN adapter IP configuration over serial"""
        if location == 'host':
            return {"error": "IP configuration on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic path Win32_NetworkAdapterConfiguration where \"Description like '%Ethernet%'\" get Description,IPAddress,IPSubnet,DefaultIPGateway"
        elif os == 'linux':
            command = f"ifconfig {interface}"  # For IP configuration in Linux
        elif os == 'edk':
            command = f"IfConfig -s {interface} dhcp"
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)
    
    
    # Retrieve LAN Power Management Information
    async def lan_power_management_logic(self, os, location):
        """Retrieve LAN power management information over serial"""
        if location == 'host':
            return {"error": "Power management on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic path Win32_NetworkAdapter where \"NetConnectionID='Ethernet'\" get PowerManagementSupported,PowerManagementCapabilities"
        elif os == 'linux':
            command = "cat /proc/acpi/wakeup"  # For power management in Linux (if supported)
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)

    # Retrieve LAN Adapter MAC Address
    async def lan_mac_address_logic(self, os, location, interface):
        """Retrieve LAN MAC address over serial"""
        if location == 'host':
            return {"error": "MAC address retrieval on host is not supported."}

        command = ""
        if os == 'windows':
            command = "wmic nic where \"NetConnectionID='Ethernet'\" get MACAddress"
        elif os == 'linux':
            command = f"cat /sys/class/net/{interface}/address"  # For MAC address in Linux
        else:
            return {"error": "Unsupported OS"}

        return await self.send_serial_command(command)
    
    async def lan_static_ip_configuration_logic(self, os, location, interface):
        """Set LAN adapter static IP configuration over serial"""
        if location == 'host':
            return {"error": "Static IP configuration on host is not supported."}

        command = ""
        if os == 'edk':
            command = f"IfConfig -s {interface} static 192.168.0.5 255.255.255.0 192.168.0.1 permanent"  # Static IP config in EDK
        else:
            return {"error": "Unsupported OS for static IP"}

        return await self.send_serial_command(command)
    
    async def lan_ping_logic(self, os, location, target_ip):
        """Ping a target IP over serial"""
        if location == 'host':
            return {"error": "Ping on host is not supported."}

        command = ""
        if os == 'edk':
            command = f"ping -n 20 {target_ip}"  # Ping with 20 requests in EDK
        else:
            return {"error": "Unsupported OS for ping"}

        return await self.send_serial_command(command)

    # Exposed Endpoints
    @exposed_http('GET', '/lan_adapter_information')
    async def lan_adapter_information(self, request: Request) -> Response:
        interface = request.rel_url.query.get('interface', 'enp1s0')
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.lan_adapter_information_logic(os, location, interface)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/lan_adapter_driver_info')
    async def lan_adapter_driver_info(self, request: Request) -> Response:
        interface = request.rel_url.query.get('interface', 'enp1s0')
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.lan_adapter_driver_info_logic(os, location, interface)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/lan_adapter_status')
    async def lan_adapter_status(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.lan_adapter_status_logic(os, location)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/lan_ip_configuration')
    async def lan_ip_configuration(self, request: Request) -> Response:
        interface = request.rel_url.query.get('interface', 'enp1s0')
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.lan_ip_configuration_logic(os, location, interface)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/lan_power_management')
    async def lan_power_management(self, request: Request) -> Response:
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.lan_power_management_logic(os, location )
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})

    @exposed_http('GET', '/lan_mac_address')
    async def lan_mac_address(self, request: Request) -> Response:
        interface = request.rel_url.query.get('interface', 'enp1s0')
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.lan_mac_address_logic(os, location, interface)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})
    
    @exposed_http('GET', '/lan_static_ip_configuration')
    async def lan_static_ip_configuration(self, request: Request) -> Response:
        interface = request.rel_url.query.get('interface', 'enp1s0')
        os, location = await self.get_params(request)
        if location == 'target':
            result = await self.lan_static_ip_configuration_logic(os, location, interface)
            return make_json_response(result)
        return make_json_response({"error": "Endpoint applicable only for target location"})
    
    @exposed_http('GET', '/lan_ping')
    async def lan_ping(self, request: Request) -> Response:

        os, location = await self.get_params(request)
        target_ip = request.rel_url.query.get('target_ip', None)
        if not target_ip:
            return make_json_response({"error": "Missing target_ip parameter"})

        if location == 'target':
            result = await self.lan_ping_logic(os, location, target_ip)
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
