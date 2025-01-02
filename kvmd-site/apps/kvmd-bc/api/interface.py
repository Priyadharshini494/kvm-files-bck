from aiohttp import web
import os
from aiohttp.web import Request
from aiohttp.web import Response
from ....htserver import exposed_http
from ....htserver import exposed_ws
from ....htserver import make_json_response
from ....htserver import WsSession
from ....logging import get_logger

# Function to determine the current USB interface
class InterfaceApi:
    def __init__(self) -> None:
        pass

    def get_current_interface(self):
        config_path = "/sys/kernel/config/usb_gadget/kvmd/configs/c.1"
        
        # Check if ACM is linked in the current configuration
        acm_link = os.path.join(config_path, "acm.usb0")
        
        # Check if NCM is linked in the current configuration
        ncm_link = os.path.join(config_path, "ncm.usb0")
        
        if os.path.islink(acm_link):
            return "ACM (Serial)"
        elif os.path.islink(ncm_link):
            return "NCM (Ethernet)"
        else:
            return "Unknown interface"

    # Define the API route to fetch the current interface
    @exposed_http('GET', '/current-interface')
    async def get_interface(self, request: Request) -> Response:
        current_interface = self.get_current_interface()
        return make_json_response({"current_interface": current_interface})

