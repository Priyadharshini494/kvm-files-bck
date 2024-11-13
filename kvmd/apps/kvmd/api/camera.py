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


from aiohttp.web import Request
from aiohttp.web import Response

from ....htserver import exposed_http
from ....htserver import make_json_response

from .Focuser import Focuser
from ....logging import get_logger
from .AutoFocus import AutoFocus
from .RpiCamera import Camera

# =====
class CameraApi:
    def __init__(
        self,
       
    ) -> None:
        pass

     # =====
    

    def move_right(self):
        motor_step=5
        i2c_bus=1
        focuser = Focuser(i2c_bus)
        focuser.set(Focuser.OPT_MOTOR_Y,focuser.get(Focuser.OPT_MOTOR_Y) + motor_step)
        get_logger(0).info("Right Camera api call ")
 
    @exposed_http("GET", "/camera/right")
    async def __right_handler(self, _: Request) -> Response:
        self.move_right()
        return make_json_response({"ok":True })
   
    def move_left(self):
        motor_step=5
        i2c_bus=1
        focuser = Focuser(i2c_bus)
        focuser.set(Focuser.OPT_MOTOR_Y,focuser.get(Focuser.OPT_MOTOR_Y) - motor_step)
        get_logger(0).info("Left Camera api call ")
 
    @exposed_http("GET", "/camera/left")
    async def __left_handler(self, _: Request) -> Response:
        self.move_left()
        return make_json_response({"ok":True })
   
    def move_down(self):
        motor_step=5
        i2c_bus=1
        focuser = Focuser(i2c_bus)
        focuser.set(Focuser.OPT_MOTOR_X,focuser.get(Focuser.OPT_MOTOR_X)- motor_step)
        get_logger(0).info("Camera down api call")
 
    @exposed_http("GET", "/camera/down")
    async def __down_handler(self, _: Request) -> Response:
        self.move_down()
        return make_json_response({"ok":True })
   
    def move_up(self):
        motor_step=5
        i2c_bus=1
        focuser = Focuser(i2c_bus)
        focuser.set(Focuser.OPT_MOTOR_X,focuser.get(Focuser.OPT_MOTOR_X)+ motor_step)
        get_logger(0).info("Camera up api call")
 
    @exposed_http("GET", "/camera/up")
    async def __up_handler(self, _: Request) -> Response:
        self.move_up()
        return make_json_response({"ok":True })
   
    def zoom_in(self):
        zoom_step = 100
        i2c_bus=1
        focuser = Focuser(i2c_bus)
        focuser.set(Focuser.OPT_ZOOM,focuser.get(Focuser.OPT_ZOOM) + zoom_step)
        get_logger(0).info("Camera zoom-in api call")
 
    @exposed_http("GET", "/camera/zoomin")
    async def __zoomin_handler(self, _: Request) -> Response:
        self.zoom_in()
        return make_json_response({"ok":True })
   
    def zoom_out(self):
        zoom_step = 100
        i2c_bus=1
        focuser = Focuser(i2c_bus)
        focuser.set(Focuser.OPT_ZOOM,focuser.get(Focuser.OPT_ZOOM) - zoom_step)
        get_logger(0).info("Camera zoom-in api call")
 
    @exposed_http("GET", "/camera/zoomout")
    async def __zoomout_handler(self, _: Request) -> Response:
        self.zoom_out()
        return make_json_response({"ok":True })
   
    def focus_in(self):
        focus_step = 100
        i2c_bus=1
        focuser = Focuser(i2c_bus)
        focuser.set(Focuser.OPT_FOCUS,focuser.get(Focuser.OPT_FOCUS)+ focus_step)
        get_logger(0).info("Camera focus-in api call")
 
    @exposed_http("GET", "/camera/focusin")
    async def __focusin_handler(self, _: Request) -> Response:
        self.focus_in()
        return make_json_response({"ok":True })
   
    def focus_out(self):
        focus_step = 100
        i2c_bus=1
        focuser = Focuser(i2c_bus)
        focuser.set(Focuser.OPT_FOCUS,focuser.get(Focuser.OPT_FOCUS)- focus_step)
        get_logger(0).info("Camera focus-out api call")
 
    @exposed_http("GET", "/camera/focusout")
    async def __focusout_handler(self, _: Request) -> Response:
        self.focus_out()
        return make_json_response({"ok":True })
    

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

   
    def auto_focus(self):
        focuser = Focuser(1)
        camera = Camera()
        auto_focus = AutoFocus(focuser,camera)
        auto_focus.startFocus()
        get_logger(0).info("Autofocus api call")
 
 
 
    @exposed_http("GET", "/camera/autofocus")
    async def __autofocus_handler(self, _: Request) -> Response:
        self.auto_focus()
        return make_json_response({"ok":True })



    