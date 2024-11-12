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

import subprocess
import time
from aiohttp.web import Request
from aiohttp.web import Response

from ....htserver import exposed_http
from ....htserver import make_json_response

from ....plugins.atx import BaseAtx

from ....validators.basic import valid_bool
from ....validators.kvm import valid_atx_power_action
from ....validators.kvm import valid_atx_button


# =====
class AtxApi:
    def __init__(self, atx: BaseAtx) -> None:
        self.__atx = atx

    # =====
        
    def execute_i2cset(self, address, register, value):
        subprocess.run(["i2cset", "-y", "1", hex(address), hex(register), hex(value)])

    def select_mux_channel(self, channel):
        subprocess.run(["i2cset", "-y", "1", "0x72", "0x00", hex(1 << channel)])

    @exposed_http("GET", "/atx")
    async def __state_handler(self, _: Request) -> Response:
        return make_json_response(await self.__atx.get_state())

    # @exposed_http("POST", "/atx/power")
    # async def __power_handler(self, request: Request) -> Response:
    #     action = valid_atx_power_action(request.query.get("action"))
    #     wait = valid_bool(request.query.get("wait", False))
    #     await ({
    #         "on": self.__atx.power_on,
    #         "off": self.__atx.power_off,
    #         "off_hard": self.__atx.power_off_hard,
    #         "reset_hard": self.__atx.power_reset_hard,
    #     }[action])(wait)
    #     return make_json_response()

    @exposed_http("GET", "/atx/power")
    async def power_operation_handler(self, request: Request) -> Response:
        try:
            self.select_mux_channel(1)
            self.execute_i2cset(0x24, 0x00, 0x3f)
            self.execute_i2cset(0x24, 0x0c, 0xc0)
           
            self.execute_i2cset(0x24, 0x12, 0x80 | 0x00)  
            time.sleep(3)
            self.execute_i2cset(0x24, 0x12, 0x00)
            return make_json_response({"message": "Power operation done"})
        except Exception as e:
            print("Error during power operation:", e)
            return make_json_response({"message": "Power operation failed."})

    # @exposed_http("POST", "/atx/click")
    # async def __click_handler(self, request: Request) -> Response:
    #     button = valid_atx_button(request.query.get("button"))
    #     wait = valid_bool(request.query.get("wait", False))
    #     await ({
    #         "power": self.__atx.click_power,
    #         "power_long": self.__atx.click_power_long,
    #         "reset": self.__atx.click_reset,
    #     }[button])(wait)
    #     return make_json_response()
        
    @exposed_http("GET", "/atx/reset")
    async def reset_operation_handler(self, request: Request) -> Response:
        try:
            self.select_mux_channel(1)
            self.execute_i2cset(0x24, 0x00, 0x3f)
            self.execute_i2cset(0x24, 0x0c, 0xc0)
           
            self.execute_i2cset(0x24, 0x12, 0x40 | 0x00)  
            time.sleep(10)
            self.execute_i2cset(0x24, 0x12, 0x00)
            return make_json_response({"message": "Reset operation done"})
        except Exception as e:
            print("Error during reset operation:", e)
            return make_json_response({"message": "Reset operation failed."})

