# ========================================================================== #
#                                                                            #
#    KVMD - The main PiKVM daemon.                                           #
#                                                                            #
#    Copyright (C) 2018-2023  Maxim Devaev <mdevaev@gmail.com>               #
#                                                                            #
#    This program is free software: you can redistribute it and/or modify    #
#    it under the terms of the GNU General Public License as published by    #
#    the Free Software Foundation, either version 3 of the License, or       #
#    (at your option) any later version.                                     #
#                                                                            #
#    This program is distributed in the hope that it will be useful,         #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of          #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           #
#    GNU General Public License for more details.                            #
#                                                                            #
#    You should have received a copy of the GNU General Public License       #
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.  #
#                                                                            #
# ========================================================================== #


import os
import stat
import functools
import struct
import serial
import asyncio
import subprocess

from .batterysimulator  import write

from aiohttp.web import Request
from aiohttp.web import Response

from ....htserver import exposed_http
from ....htserver import make_json_response

from .Focuser import Focuser
from ....logging import get_logger
from .AutoFocus import AutoFocus
from .RpiCamera import Camera

# =====
class BatteryApi:
    def __init__(
        self,
       
    ) -> None:
        pass

     # =====

   
    @exposed_http("POST", "/battery/set_simulation_percent")
    async def set_simulation_percent(self, request: Request) -> Response:
        data = await request.json()
        percent = data.get('percent')
        hex_value = hex(percent // 10)
        formatted_str = '0x' + hex_value[2:].zfill(1)
        write(15,percent,"simulated")
        return make_json_response({"ok": True, "message": "Simulation Percentage set!", "percent": [formatted_str, percent]})

    @exposed_http("POST", "/battery/simulated")
    async def set_simulated_battery_mode(self, request: Request) -> Response:
        write(None,None,"simulated-attach")
        return make_json_response({"ok": True, "message": "Mode set to Simulated battery"})
    
    @exposed_http("POST", "/battery/real")
    async def set_real_battery_mode(self, request: Request) -> Response:
        write(None,None,"real-attach")
        return make_json_response({"ok": True, "message": "Mode set to real battery"})
    
    @exposed_http("POST", "/battery/ac-source")
    async def set_ac_source_battery_mode(self, request: Request) -> Response:
        commands = [
            ["raspi-gpio", "set", "24", "op", "dl"],
            ["raspi-gpio", "set", "13", "op", "dl"]

        ]
        for command_args in commands:
            subprocess.run(command_args)
        return make_json_response({"ok": True, "message": "Mode set to AC source"})

    

   

    @exposed_http("GET", "/postcode/get_data")
    async def __getData_handler(self, request: Request) -> Response:
        ser = serial.Serial('/dev/ttyAMA0', 115200, timeout=1)
        iteration_count = 0  
 
        try:
            while True:
                line = await asyncio.to_thread(ser.readline)
                if line:
                    line = line.decode('utf-8', errors='replace').strip()
                    result = {"data": line}
                    return make_json_response(result)
                iteration_count += 1
                if iteration_count >= 50:
                    break
 
        except asyncio.TimeoutError:
            pass
        finally:
            ser.close()
 
        iteration_count = 0

   
    
 
    


    