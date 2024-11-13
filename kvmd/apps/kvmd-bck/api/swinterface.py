import re
import os
import stat
import functools
import struct
import serial
from aiohttp.web import Request
from aiohttp.web import Response
from aiohttp import web
from ....htserver import exposed_http
from ....htserver import exposed_ws
from ....htserver import make_json_response
from ....logging import get_logger
 
import subprocess
import asyncio
from functools import wraps

 
class switchInterfaceApi:
    def __init__(self) -> None:
        pass
 
    async def execute_command(self,command):
        try:
            await asyncio.to_thread(subprocess.run, command, shell=True, check=True)
            return True, None
        except subprocess.CalledProcessError as e:
            return False, str(e)
 
    @exposed_http('POST', '/enable_acm')
    async def enable_acm(self, request):
        try:
            # List of commands to execute
            commands = [
                "sudo /bin/sh -c 'echo \"\" > /sys/kernel/config/usb_gadget/kvmd/UDC'",
                "sudo /bin/rm /sys/kernel/config/usb_gadget/kvmd/configs/c.1/ncm.usb0",
                "sudo /bin/ln -s /sys/kernel/config/usb_gadget/kvmd/functions/acm.usb0 /sys/kernel/config/usb_gadget/kvmd/configs/c.1",
                "sudo /bin/sh -c 'echo fe980000.usb > /sys/kernel/config/usb_gadget/kvmd/UDC'"
            ]

            # Execute each command and handle errors
            for command in commands:
                success, error = await self.execute_command(command)
                if not success:
                    return make_json_response({"status": "error", "message": f"Command failed: {error}"}, status=500)

            return make_json_response({"status": "success", "message": "ACM mode enabled successfully."}, status=200)
        
        except Exception as e:
            return make_json_response({"status": "error", "message": str(e)}, status=500)
    
    @exposed_http('POST', '/enable_ncm')
    async def enable_ncm(self, request):
        try:
            commands = [
                "sudo /bin/sh -c 'echo \"\" > /sys/kernel/config/usb_gadget/kvmd/UDC'",
                "sudo /bin/rm /sys/kernel/config/usb_gadget/kvmd/configs/c.1/acm.usb0",
                "sudo /bin/mkdir -p /sys/kernel/config/usb_gadget/kvmd/functions/ncm.usb0",
                "sudo /bin/ln -s /sys/kernel/config/usb_gadget/kvmd/functions/ncm.usb0 /sys/kernel/config/usb_gadget/kvmd/configs/c.1",
                "sudo /bin/sh -c 'echo fe980000.usb > /sys/kernel/config/usb_gadget/kvmd/UDC'"
            ]
    
            for command in commands:
                success, error = await self.execute_command(command)
                if not success:
                    return make_json_response({"status": "error", "message": f"Command failed: {error}"}, status=500)
    
            return make_json_response({"status": "success", "message": "NCM mode enabled successfully."}, status=200)
    
        except Exception as e:
            return make_json_response({"status": "error", "message": str(e)}, status=500)
 
    # app = web.Application()
 
    # # Iterate over a copy of the keys from globals()
    # for attr_name in list(globals().keys()):
    #     attr = globals()[attr_name]
    #     if callable(attr) and hasattr(attr, '__expose__'):
    #         method, path = attr.__expose__
    #         if method.upper() == 'GET':
    #             app.router.add_get(path, attr)
    #         elif method.upper() == 'POST':
    #             app.router.add_post(path, attr)
 
    # if __name__ == "__main__":
    #     web.run_app(app, host="0.0.0.0", port=8000)
