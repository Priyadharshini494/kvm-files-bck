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


import asyncio
import operator
import dataclasses
import os
import signal
import json

from typing import Tuple
from typing import List
from typing import Dict
from typing import Callable
from typing import Coroutine
from typing import AsyncGenerator
from typing import Optional
from typing import Any

from aiohttp import web
from aiohttp.web import Request
from aiohttp.web import Response
from aiohttp.web import FileResponse, HTTPNotFound
from aiohttp.web import WebSocketResponse

from ...logging import get_logger

from ...errors import OperationError

from ... import aiotools
from ... import aioproc

from ...htserver import HttpExposed
from ...htserver import exposed_http
from ...htserver import exposed_ws
from ...htserver import make_json_response
from ...htserver import WsSession
from ...htserver import HttpServer

from ...plugins import BasePlugin
from ...plugins.hid import BaseHid
from ...plugins.atx import BaseAtx
from ...plugins.msd import BaseMsd

from ...validators.basic import valid_bool
from ...validators.kvm import valid_stream_quality
from ...validators.kvm import valid_stream_fps
from ...validators.kvm import valid_stream_resolution
from ...validators.kvm import valid_stream_h264_bitrate
from ...validators.kvm import valid_stream_h264_gop

from .auth import AuthManager
from .info import InfoManager
from .info import InfoManager2
from .info import InfoManager3
from .info import InfoManager4
from .logreader import LogReader
from .ugpio import UserGpio
from .streamer import Streamer
from  .streamer2 import Streamer2
from  .streamer3 import Streamer3
from  .streamer4 import Streamer4
from .snapshoter import Snapshoter
from .ocr import Ocr

from .api.auth import AuthApi
from .api.auth import check_request_auth

from .api.info import InfoApi
from .api.info import InfoApi2
from .api.info import InfoApi3
from .api.info import InfoApi4
from .api.log import LogApi
from .api.ugpio import UserGpioApi
from .api.hid import HidApi
from .api.apc import ApcApi
from .api.getbinfiles import GetbinfilesApi
from .api.flashos import FlashosApi
from .api.flashifwi import FlashifwiApi
from .api.bootorder import GetBootorderApi
from .api.resetedk import ResetEdkApi
from .api.interface import InterfaceApi
from .api.usbserial import UsbserialApi
from .api.usbethernet import UsbethernetApi
from .api.usbethernet import UdpHandler
from .api.pcitestcase import PciApi
from .api.usbtestcase import UsbApi
from .api.bluetoothtestcase import BluetoothApi
from .api.wifitestcase import WiFiApi
from .api.lantestcase import LanApi
from .api.rastestcase import RasApi
from .api.camera import CameraApi
from .api.battery import BatteryApi
from .api.atx import AtxApi
from .api.msd import MsdApi
from .api.streamer import StreamerApi
from .api.streamer2 import StreamerApi2
from .api.streamer3 import StreamerApi3
from .api.streamer4 import StreamerApi4
from .api.export import ExportApi
from .api.redfish import RedfishApi
from .api.swinterface import switchInterfaceApi

# =====
class StreamerQualityNotSupported(OperationError):
    def __init__(self) -> None:
        super().__init__("This streamer does not support quality settings")


class StreamerResolutionNotSupported(OperationError):
    def __init__(self) -> None:
        super().__init__("This streamer does not support resolution settings")


class StreamerH264NotSupported(OperationError):
    def __init__(self) -> None:
        super().__init__("This streamer does not support H264")


# =====
@dataclasses.dataclass(frozen=True)
class _Component:  # pylint: disable=too-many-instance-attributes
    name: str
    event_type: str
    obj: object
    sysprep: Optional[Callable[[], None]] = None
    systask: Optional[Callable[[], Coroutine[Any, Any, None]]] = None
    get_state: Optional[Callable[[], Coroutine[Any, Any, Dict]]] = None
    poll_state: Optional[Callable[[], AsyncGenerator[Dict, None]]] = None
    cleanup: Optional[Callable[[], Coroutine[Any, Any, Dict]]] = None

    def __post_init__(self) -> None:
        if isinstance(self.obj, BasePlugin):
            object.__setattr__(self, "name", f"{self.name} ({self.obj.get_plugin_name()})")

        for field in ["sysprep", "systask", "get_state", "poll_state", "cleanup"]:
            object.__setattr__(self, field, getattr(self.obj, field, None))
        if self.get_state or self.poll_state:
            assert self.event_type, self


class KvmdServer(HttpServer):  # pylint: disable=too-many-arguments,too-many-instance-attributes
    def __init__(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        auth_manager: AuthManager,
        info_manager: InfoManager,
        info_manager2: InfoManager2, 
        info_manager3: InfoManager3, 
        info_manager4: InfoManager4, 
        log_reader: (LogReader | None),
        user_gpio: UserGpio,
        ocr: Ocr,

        hid: BaseHid,
        atx: BaseAtx,
        msd: BaseMsd,
        streamer: Streamer,
        streamer2: Streamer2,
        streamer3: Streamer3,
        streamer4: Streamer4,
        snapshoter: Snapshoter,

        keymap_path: str,
        ignore_keys: List[str],
        mouse_x_range: Tuple[int, int],
        mouse_y_range: Tuple[int, int],

        stream_forever: bool,
        stream_forever2: bool,
        stream_forever3: bool,
        stream_forever4: bool,
    ) -> None:

        super().__init__()

        self.__auth_manager = auth_manager
        self.__hid = hid
        self.__streamer = streamer
        self.__streamer2 = streamer2
        self.__streamer3 = streamer3
        self.__streamer4 = streamer4
        self.__snapshoter = snapshoter  # Not a component: No state or cleanup
        self.__user_gpio = user_gpio  # Has extra state "gpio_scheme_state"
        self.__system_tasks: List[asyncio.Task] = []
        self.__stream_forever = stream_forever
        self.__stream_forever2 = stream_forever2
        self.__stream_forever3 = stream_forever3
        self.__stream_forever4 = stream_forever4
        self.__components = [
            *[
                _Component("Auth manager", "", auth_manager),
            ],
            *[
                _Component(f"Info manager ({sub})", f"info_{sub}_state", info_manager.get_submanager(sub))
                for sub in sorted(info_manager.get_subs())
            ],
            *[
                _Component("User-GPIO",    "gpio_state",     user_gpio),
                _Component("HID",          "hid_state",      hid),
                _Component("ATX",          "atx_state",      atx),
                _Component("MSD",          "msd_state",      msd),
                _Component("Streamer",     "streamer_state", streamer),
                _Component("Streamer2",    "streamer_state", streamer2),
                _Component("Streamer3",    "streamer_state", streamer3),
                _Component("Streamer4",    "streamer_state", streamer4),
            ],
            #*[
            #    _Component(f"Info manager2 ({sub})", f"info_{sub}_state", info_manager2.get_submanager(sub))
            #    for sub in sorted(info_manager2.get_subs())
            #],
 
        ]
        self._udphandler_api = UdpHandler()
        self.__switchInterface_api=switchInterfaceApi()
        self.__bootorder_api = GetBootorderApi()
        self.__flashos_api = FlashosApi()
        self.__resetedk_api = ResetEdkApi()
        self.__flashifwi_api = FlashifwiApi()
        self.__getbinfiles_api = GetbinfilesApi()
        self.__interface_api = InterfaceApi()
        self.__usbserial_api = UsbserialApi()
        self.__usbethernet_api = UsbethernetApi(self._udphandler_api)
        self.__pcitestcase_api = PciApi()
        self.__usbtestcase_api = UsbApi()
        self.__bluetoothtestcase_api = BluetoothApi()
        self.__wifitestcase_api = WiFiApi()
        self.__lantestcase_api = LanApi()
        self.__rastestcase_api = RasApi()
        self.__apc_api = ApcApi()
        self.__hid_api = HidApi(hid, keymap_path, ignore_keys, mouse_x_range, mouse_y_range)  # Ugly hack to get keymaps state
        self.__camera_api = CameraApi()
        self.__battery_api = BatteryApi()
        self.__streamer_api = StreamerApi(streamer,ocr)  # Same hack to get ocr langs state
        self.__apis: List[object] = [
            self,
            AuthApi(auth_manager),
            InfoApi(info_manager),
            InfoApi2(info_manager2),
            InfoApi3(info_manager3),
            InfoApi4(info_manager4),
            LogApi(log_reader),
            UserGpioApi(user_gpio),
            self.__hid_api,
            self.__apc_api,
            self.__bootorder_api,
            self.__flashos_api,
            self.__resetedk_api,
            self.__flashifwi_api,
            self.__interface_api,
            self.__getbinfiles_api,
            self.__usbserial_api,
            self._udphandler_api,
            self.__usbethernet_api,
            self.__pcitestcase_api,
            self.__usbtestcase_api,
            self.__bluetoothtestcase_api,
            self.__wifitestcase_api,
            self.__lantestcase_api,
            self.__rastestcase_api,
            self.__camera_api,
            self.__battery_api,
            self.__switchInterface_api,
            AtxApi(atx),
            MsdApi(msd),
           # self.__streamer_api,
            StreamerApi(streamer,ocr),
            StreamerApi2(streamer2,ocr),
            StreamerApi3(streamer3,ocr),
            StreamerApi4(streamer4,ocr),
            ExportApi(info_manager, atx, user_gpio),
            RedfishApi(info_manager, atx),
        ]

        self.__streamer_notifier = aiotools.AioNotifier()
        self.__reset_streamer = False
        self.__new_streamer_params: Dict = {}
        self.__streamer_notifier2 = aiotools.AioNotifier()
        self.__reset_streamer2 = False
        self.__new_streamer_params2: Dict = {}
        self.__streamer_notifier3 = aiotools.AioNotifier()
        self.__reset_streamer3 = False
        self.__new_streamer_params3: Dict = {}
        self.__streamer_notifier4 = aiotools.AioNotifier()
        self.__reset_streamer4 = False
        self.__new_streamer_params4: Dict = {}

    # ===== STREAMER CONTROLLER

    @exposed_http("POST", "/streamer/set_params")
    async def __streamer_set_params_handler(self, request: Request) -> Response:
        current_params = self.__streamer.get_params()
        for (name, validator, exc_cls) in [
            ("quality", valid_stream_quality, StreamerQualityNotSupported),
            ("desired_fps", valid_stream_fps, None),
            ("resolution", valid_stream_resolution, StreamerResolutionNotSupported),
            ("h264_bitrate", valid_stream_h264_bitrate, StreamerH264NotSupported),
            ("h264_gop", valid_stream_h264_gop, StreamerH264NotSupported),
        ]:
            value = request.query.get(name)
            if value:
                if name not in current_params:
                    assert exc_cls is not None, name
                    raise exc_cls()
                value = validator(value)  # type: ignore
                if current_params[name] != value:
                    self.__new_streamer_params[name] = value
        self.__streamer_notifier.notify()
        return make_json_response()

    @exposed_http("POST", "/streamer/reset")
    async def __streamer_reset_handler(self, _: Request) -> Response:
        self.__reset_streamer = True
        self.__streamer_notifier.notify()
        return make_json_response()
    
    @exposed_http("POST", "/streamer2/set_params")
    async def __streamer_set_params_handler2(self, request: Request) -> Response:
        current_params = self.__streamer2.get_params()
        for (name, validator, exc_cls) in [
            ("quality", valid_stream_quality, StreamerQualityNotSupported),
            ("desired_fps", valid_stream_fps, None),
            ("resolution", valid_stream_resolution, StreamerResolutionNotSupported),
            ("h264_bitrate", valid_stream_h264_bitrate, StreamerH264NotSupported),
            ("h264_gop", valid_stream_h264_gop, StreamerH264NotSupported),
        ]:
            value = request.query.get(name)
            if value:
                if name not in current_params:
                    assert exc_cls is not None, name
                    raise exc_cls()
                value = validator(value)  # type: ignore
                if current_params[name] != value:
                    self.__new_streamer_params2[name] = value
        self.__streamer_notifier2.notify()
        return make_json_response()

    @exposed_http("POST", "/streamer2/reset")
    async def __streamer_reset_handler2(self, _: Request) -> Response:
        self.__reset_streamer2 = True
        self.__streamer_notifier2.notify()
        return make_json_response()
    

    @exposed_http("POST", "/streamer3/set_params")
    async def __streamer_set_params_handler3(self, request: Request) -> Response:
        current_params = self.__streamer3.get_params()
        for (name, validator, exc_cls) in [
            ("quality", valid_stream_quality, StreamerQualityNotSupported),
            ("desired_fps", valid_stream_fps, None),
            ("resolution", valid_stream_resolution, StreamerResolutionNotSupported),
            ("h264_bitrate", valid_stream_h264_bitrate, StreamerH264NotSupported),
            ("h264_gop", valid_stream_h264_gop, StreamerH264NotSupported),
        ]:
            value = request.query.get(name)
            if value:
                if name not in current_params:
                    assert exc_cls is not None, name
                    raise exc_cls()
                value = validator(value)  # type: ignore
                if current_params[name] != value:
                    self.__new_streamer_params3[name] = value
        self.__streamer_notifier3.notify()
        return make_json_response()

    @exposed_http("POST", "/streamer3/reset")
    async def __streamer_reset_handler3(self, _: Request) -> Response:
        self.__reset_streamer3 = True
        self.__streamer_notifier3.notify()
        return make_json_response()
    

    @exposed_http("POST", "/streamer4/set_params")
    async def __streamer_set_params_handler4(self, request: Request) -> Response:
        current_params = self.__streamer4.get_params()
        for (name, validator, exc_cls) in [
            ("quality", valid_stream_quality, StreamerQualityNotSupported),
            ("desired_fps", valid_stream_fps, None),
            ("resolution", valid_stream_resolution, StreamerResolutionNotSupported),
            ("h264_bitrate", valid_stream_h264_bitrate, StreamerH264NotSupported),
            ("h264_gop", valid_stream_h264_gop, StreamerH264NotSupported),
        ]:
            value = request.query.get(name)
            if value:
                if name not in current_params:
                    assert exc_cls is not None, name
                    raise exc_cls()
                value = validator(value)  # type: ignore
                if current_params[name] != value:
                    self.__new_streamer_params4[name] = value
        self.__streamer_notifier4.notify()
        return make_json_response()

    @exposed_http("POST", "/streamer4/reset")
    async def __streamer_reset_handler4(self, _: Request) -> Response:
        self.__reset_streamer4 = True
        self.__streamer_notifier4.notify()
        return make_json_response()

    # ===== WEBSOCKET

#     @exposed_http("GET", "/ws")
#     async def __ws_handler(self, request: Request) -> WebSocketResponse:
#          stream = valid_bool(request.query.get("stream", True))
#          async with self._ws_session(request, stream=stream) as ws:
#              stage1 = [
#                  ("gpio_model_state", self.__user_gpio.get_model()),
#                  ("hid_keymaps_state", self.__hid_api.get_keymaps()),
#                  ("streamer_ocr_state", self.__streamer_api.get_ocr()),
                
#              ]
#              stage2 = [
#                  (comp.event_type, comp.get_state())
#                  for comp in self.__components
#                  if comp.get_state
#              ]
#              stages = stage1 + stage2
# #             events = dict(zip(
#  #                map(operator.itemgetter(0), stages),
#   #               await asyncio.gather(*map(operator.itemgetter(1), stages)),
#    #          ))
#              results = await asyncio.gather(*map(operator.itemgetter(1), stages))
#              events = list(zip(map(operator.itemgetter(0), stages), results))
#              for stage in [stage1, stage2]:
#                  await asyncio.gather(*[
#                  ws.send_event(event_type, data)
#                  for (event_type, data) in events if event_type not in [et for (et, _) in stage]
#                 ])
#             # for stage in [stage1, stage2]:
#             #     await asyncio.gather(*[
#             #         ws.send_event(event_type, events.pop(event_type))
#             #         for (event_type, _) in stage
#             #     ])
#              await ws.send_event("loop", {})
#              return (await self._ws_loop(ws))

    # @exposed_http("GET", "/ws")
    # async def __ws_handler(self, request: Request) -> WebSocketResponse:
    #    stream = valid_bool(request.query.get("stream", True))
    #    logger = get_logger(0)
    #    async with self._ws_session(request, stream=stream) as ws:
    #        stage1 = [
    #            ("gpio_model_state", await self.__user_gpio.get_model()),
    #            ("hid_keymaps_state", await self.__hid_api.get_keymaps()),
    #            ("streamer_ocr_state", await self.__streamer_api.get_ocr()),
    #         ]
    #        stage2 = [
    #            (comp.event_type, await comp.get_state())
    #            for comp in self.__components
    #            if comp.get_state
    #        ]
    #        logger.info("Stage2:", stage2)
    #        stages = stage1 + stage2
    #        events = dict(stages)  # Convert to a dictionary
    #        for stage in [stage1, stage2]:
    #            await asyncio.gather(*[
    #                ws.send_event(event_type, events[event_type])
    #                for (event_type, _) in stage
    #                if event_type in events
    #            ])
    #        await ws.send_event("loop", {})
    #        return await self._ws_loop(ws)

    
    @exposed_http("GET", "/swagger")
    async def serve_swagger_ui(self, _:Request) -> Response:
        swagger_ui_path = '/usr/share/kvmd/web/swagger-index.html'
        if os.path.exists(swagger_ui_path):
            return Response(text=open(swagger_ui_path).read(), content_type='text/html')
        else:
            raise HTTPNotFound(text="Swagger UI not found")

    @exposed_http("GET", "/swagger.json")
    async def swagger_json_handler(self, _: Request) -> Response:
        swagger_data = {
    "openapi": "3.0.3",
    "info": {
        "title": "Rutomatrix Swagger - OpenAPI 3.0",
        "description": "This is a sample Rutomatrix API Server based on the OpenAPI 3.0 specification. You can learn more about Swagger at https://swagger.io. In this version of the Rutomatrix API, weâ€™ve embraced the design-first approach! This allows us to collaborate more efficiently and continuously improve the API. Whether you're contributing to the API's code or making changes to the definition, your feedback will help us make the API more robust and feature-rich over time.",
        "termsOfService": "http://swagger.io/terms/",
        "contact": {
            "email": "ruto111222@gmail.com"
        },
        "license": {
            "name": "Apache 2.0",
            "url": "http://www.apache.org/licenses/LICENSE-2.0.html"
        },
        "version": "1.0.11"
    },
    "externalDocs": {
        "description": "Find out more about Swagger",
        "url": "http://swagger.io"
    },
    "servers": [
        {
            "url": "https://10.208.57.90/api/"
        }
    ],
    "tags": [
        {
            "name": "Streamer",
            "description": "Information about the streamers of Rutomatrix"
        },
        {
            "name": "Informations",
            "description": "Everything about system information and authorisation"
        },
        {
            "name": "Features",
            "description": "Below are the features of Rutomatrix"
        },
        {
            "name": "Power",
            "description": "Operations related to the Power features of Rutomatrix"
        },
        {
            "name": "Firmware",
            "description": "Operations related to the Firmware features of Rutomatrix"
        },
        {
            "name": "EDK",
            "description": "Operations related to the EDK features of Rutomatrix"
        },
        {
            "name": "Postcode",
            "description": "Operations related to the battery features of Rutomatrix"
        },
        {
            "name": "Hid events",
            "description": "Operations related to the Hid events of Rutomatrix"
        },
        {
            "name": "Camera",
            "description": "Operations related to the Camera features of Rutomatrix"
        },
        {
            "name": "Interface",
            "description": "Operations related to the Serial and ethernet features of Rutomatrix"
        },
        {
            "name": "Mass storage",
            "description": "Operations related to the Mass storage features of Rutomatrix"
        },
        {
            "name": "BMC",
            "description": "Operations related to the BMC features of Rutomatrix"
        },
        {
            "name": "Battery",
            "description": "Operations related to the battery features of Rutomatrix"
        },
        {
            "name": "Testcases",
            "description": "Domain specific Testcases of Rutomatrix"
        },
        {
            "name": "PCI_Testcase",
            "description": "PCIE domain specific testcases of Rutomatrix"
        },
        {
            "name": "USB_Testcase",
            "description" : "USB domain specific tescases of Rutomatrix"
        },
        {
            "name": "Bluetooth_Testcase",
            "description": "Bluetooth domain specific testcases of Rutomatrix"
        },
        {
            "name": "WiFi_Testcase",
            "description": "WiFi domain specific testcases of Rutomatrix"
        },
        {
            "name": "LAN_Testcase",
            "description": "LAN domain specific testcases of Rutomatrix"
        }
    ],
    "paths": {
        "/streamer/set_params": {
            "post": {
                "tags": [
                    "Streamer"
                ],
                "summary": "Set parameters for streamer 1",
                "operationId": "setStreamerParams",
                "parameters": [
                    {
                        "name": "quality",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "description": "Stream quality (e.g., 'high', 'medium', 'low')."
                        }
                    },
                    {
                        "name": "desired_fps",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "description": "Desired frames per second."
                        }
                    },
                    {
                        "name": "resolution",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "description": "Resolution (e.g., '1920x1080')."
                        }
                    },
                    {
                        "name": "h264_bitrate",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "description": "H.264 bitrate."
                        }
                    },
                    {
                        "name": "h264_gop",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "description": "H.264 GOP (Group of Pictures)."
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "success"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Parameters set successfully."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "error"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Invalid parameters."
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/streamer/reset": {
            "post": {
                "tags": [
                    "Streamer"
                ],
                "summary": "Reset streamer 1",
                "operationId": "resetStreamer",
                "responses": {
                    "200": {
                        "description": "Successful reset",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "success"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Streamer reset successfully."
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/streamer2/set_params": {
            "post": {
                "tags": [
                    "Streamer"
                ],
                "summary": "Set parameters for streamer 2",
                "operationId": "setStreamer2Params",
                "parameters": [
                    {
                        "name": "quality",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "description": "Stream quality."
                        }
                    },
                    {
                        "name": "desired_fps",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "description": "Desired frames per second."
                        }
                    },
                    {
                        "name": "resolution",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "description": "Resolution."
                        }
                    },
                    {
                        "name": "h264_bitrate",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "description": "H.264 bitrate."
                        }
                    },
                    {
                        "name": "h264_gop",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "description": "H.264 GOP."
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "success"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Parameters set successfully."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "error"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Invalid parameters."
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/streamer2/reset": {
            "post": {
                "tags": [
                    "Streamer"
                ],
                "summary": "Reset streamer 2",
                "operationId": "resetStreamer2",
                "responses": {
                    "200": {
                        "description": "Successful reset",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "success"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Streamer reset successfully."
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/streamer3/set_params": {
            "post": {
                "tags": [
                    "Streamer"
                ],
                "summary": "Set parameters for streamer 3",
                "operationId": "setStreamer3Params",
                "parameters": [
                    {
                        "name": "quality",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "description": "Stream quality."
                        }
                    },
                    {
                        "name": "desired_fps",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "description": "Desired frames per second."
                        }
                    },
                    {
                        "name": "resolution",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "description": "Resolution."
                        }
                    },
                    {
                        "name": "h264_bitrate",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "description": "H.264 bitrate."
                        }
                    },
                    {
                        "name": "h264_gop",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "description": "H.264 GOP."
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "success"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Parameters set successfully."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "error"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Invalid parameters."
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/streamer3/reset": {
            "post": {
                "tags": [
                    "Streamer"
                ],
                "summary": "Reset streamer 3",
                "operationId": "resetStreamer3",
                "responses": {
                    "200": {
                        "description": "Successful reset",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "success"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Streamer reset successfully."
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/streamer4/set_params": {
            "post": {
                "tags": [
                    "Streamer"
                ],
                "summary": "Set parameters for streamer 4",
                "operationId": "setStreamer4Params",
                "parameters": [
                    {
                        "name": "quality",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "description": "Stream quality."
                        }
                    },
                    {
                        "name": "desired_fps",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "description": "Desired frames per second."
                        }
                    },
                    {
                        "name": "resolution",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "description": "Resolution."
                        }
                    },
                    {
                        "name": "h264_bitrate",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "description": "H.264 bitrate."
                        }
                    },
                    {
                        "name": "h264_gop",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "description": "H.264 GOP."
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "success"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Parameters set successfully."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "error"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Invalid parameters."
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/streamer4/reset": {
            "post": {
                "tags": [
                    "Streamer"
                ],
                "summary": "Reset streamer 4",
                "operationId": "resetStreamer4",
                "responses": {
                    "200": {
                        "description": "Successful reset",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "success"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Streamer reset successfully."
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/apc-power-off": {
            "post": {
                "tags": [
                    "Power"
                ],
                "summary": "Power off APC PDU outlet",
                "operationId": "apcPowerOff",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "ip_address": {
                                        "type": "string",
                                        "description": "IP address of the PDU"
                                    },
                                    "username": {
                                        "type": "string",
                                        "description": "Username for PDU access"
                                    },
                                    "password": {
                                        "type": "string",
                                        "description": "Password for PDU access"
                                    }
                                },
                                "required": [
                                    "ip_address",
                                    "username",
                                    "password"
                                ]
                            },
                            "example": {
                                "ip_address": "192.168.1.100",
                                "username": "admin",
                                "password": "password123"
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Successful power off operation",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {
                                            "type": "string",
                                            "example": "Power off successful."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad request",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "IP address, username, and password are required fields."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Server error",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "An error occurred processing the request."
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/apc-power-on": {
            "post": {
                "tags": [
                    "Power"
                ],
                "summary": "Power on APC PDU outlet",
                "operationId": "apcPowerOn",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "ip_address": {
                                        "type": "string",
                                        "description": "IP address of the PDU"
                                    },
                                    "username": {
                                        "type": "string",
                                        "description": "Username for PDU access"
                                    },
                                    "password": {
                                        "type": "string",
                                        "description": "Password for PDU access"
                                    }
                                },
                                "required": [
                                    "ip_address",
                                    "username",
                                    "password"
                                ]
                            },
                            "example": {
                                "ip_address": "192.168.1.100",
                                "username": "admin",
                                "password": "password123"
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Successful power on operation",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {
                                            "type": "string",
                                            "example": "Power on operation successful."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad request",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "IP address, username, and password are required fields."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Server error",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "An error occurred processing the request."
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/atx": {
            "get": {
                "tags": [
                    "Power"
                ],
                "summary": "Get ATX state",
                "operationId": "getAtxState",
                "responses": {
                    "200": {
                        "description": "Returns the current ATX state",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "state": {
                                            "type": "string",
                                            "example": "on"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/atx/power": {
            "get": {
                "tags": [
                    "Power"
                ],
                "summary": "Perform ATX power operation",
                "operationId": "performAtxPowerOperation",
                "responses": {
                    "200": {
                        "description": "Power operation successful",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {
                                            "type": "string",
                                            "example": "Power operation done"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Power operation failed",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {
                                            "type": "string",
                                            "example": "Power operation failed."
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/atx/reset": {
            "get": {
                "tags": [
                    "Power"
                ],
                "summary": "Perform ATX reset operation",
                "operationId": "performAtxResetOperation",
                "responses": {
                    "200": {
                        "description": "Reset operation successful",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {
                                            "type": "string",
                                            "example": "Reset operation done"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Reset operation failed",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {
                                            "type": "string",
                                            "example": "Reset operation failed."
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/auth/login": {
            "post": {
                "tags": [
                    "Informations"
                ],
                "summary": "Login and retrieve auth token",
                "operationId": "login",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/x-www-form-urlencoded": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "user": {
                                        "type": "string",
                                        "description": "The username",
                                        "example": "admin"
                                    },
                                    "passwd": {
                                        "type": "string",
                                        "description": "The password",
                                        "example": "admin123"
                                    }
                                },
                                "required": [
                                    "user",
                                    "passwd"
                                ]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Login successful, auth token returned",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "auth_token": {
                                            "type": "string",
                                            "description": "The authentication token",
                                            "example": "abc123token"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "403": {
                        "description": "Login failed",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "Forbidden"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/auth/logout": {
            "post": {
                "tags": [
                    "Informations"
                ],
                "summary": "Logout and invalidate the auth token",
                "operationId": "logout",
                "responses": {
                    "200": {
                        "description": "Logout successful"
                    }
                }
            }
        },
        "/auth/check": {
            "get": {
                "tags": [
                    "Informations"
                ],
                "summary": "Check if the user is authenticated",
                "operationId": "checkAuth",
                "responses": {
                    "200": {
                        "description": "User is authenticated"
                    },
                    "401": {
                        "description": "User is not authenticated",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "Unauthorized"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/battery/set_simulation_percent": {
            "post": {
                "tags": [
                    "Battery"
                ],
                "summary": "Set the simulation percentage for the battery",
                "operationId": "setSimulationPercent",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "percent": {
                                        "type": "integer",
                                        "description": "The simulation percentage (0-100)",
                                        "example": 50
                                    }
                                },
                                "required": [
                                    "percent"
                                ]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Simulation percentage set successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Simulation Percentage set!"
                                        },
                                        "percent": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            },
                                            "example": [
                                                "0x5",
                                                50
                                            ]
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/battery/simulated": {
            "post": {
                "tags": [
                    "Battery"
                ],
                "summary": "Set the battery mode to simulated",
                "operationId": "setSimulatedBatteryMode",
                "responses": {
                    "200": {
                        "description": "Battery mode set to simulated",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Mode set to Simulated battery"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/battery/real": {
            "post": {
                "tags": [
                    "Battery"
                ],
                "summary": "Set the battery mode to real",
                "operationId": "setRealBatteryMode",
                "responses": {
                    "200": {
                        "description": "Battery mode set to real",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Mode set to real battery"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/battery/ac-source": {
            "post": {
                "tags": [
                    "Battery"
                ],
                "summary": "Set the battery mode to AC source",
                "operationId": "setAcSourceBatteryMode",
                "responses": {
                    "200": {
                        "description": "Battery mode set to AC source",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Mode set to AC source"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/get-bootorder-edk": {
            "post": {
                "tags": [
                    "EDK"
                ],
                "summary": "Retrieve boot order from the device",
                "operationId": "getBootOrder",
                "responses": {
                    "200": {
                        "description": "Command processed successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {
                                            "type": "string",
                                            "example": "Command processed successfully"
                                        },
                                        "response": {
                                            "type": "string",
                                            "description": "Response data from the serial device",
                                            "example": "Boot order: 1, 2, 3"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "An error occurred processing the request",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "Failed to open serial connection"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/reset-edk": {
            "post": {
                "tags":[
                    "EDK"
                ],
            "summary": "Reset the EDK",
            "operationId": "resetEdk",
            "requestBody": {
          "required": True,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "param1": {
                    "type": "string",
                    "description": "Description of param1"
                  },
                  "param2": {
                    "type": "string",
                    "description": "Description of param2"
                  }
                },
                "required": ["param1", "param2"]
              }
            }
          }
          },
          "responses": {
          "200": {
            "description": "EDK reset successful",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "message": {
                      "type": "string",
                      "description": "Success message"
                    }
                  }
                }
              }
            }
          },
          "500": {
            "description": "Internal Server Error",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "description": "Error message"
                    }
                  }
                }
              }
            }
          }
          }
          }
        },
        "/camera/right": {
            "get": {
                "tags": [
                    "Camera"
                ],
                "summary": "Move camera to the right",
                "operationId": "moveCameraRight",
                "responses": {
                    "200": {
                        "description": "Camera moved to the right successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {
                                            "type": "boolean",
                                            "example": True
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/camera/left": {
            "get": {
                "tags": [
                    "Camera"
                ],
                "summary": "Move camera to the left",
                "operationId": "moveCameraLeft",
                "responses": {
                    "200": {
                        "description": "Camera moved to the left successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {
                                            "type": "boolean",
                                            "example": True
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/camera/down": {
            "get": {
                "tags": [
                    "Camera"
                ],
                "summary": "Move camera down",
                "operationId": "moveCameraDown",
                "responses": {
                    "200": {
                        "description": "Camera moved down successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {
                                            "type": "boolean",
                                            "example": True
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/camera/up": {
            "get": {
                "tags": [
                    "Camera"
                ],
                "summary": "Move camera up",
                "operationId": "moveCameraUp",
                "responses": {
                    "200": {
                        "description": "Camera moved up successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {
                                            "type": "boolean",
                                            "example": True
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/camera/zoomin": {
            "get": {
                "tags": [
                    "Camera"
                ],
                "summary": "Zoom in the camera",
                "operationId": "zoomCameraIn",
                "responses": {
                    "200": {
                        "description": "Camera zoomed in successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {
                                            "type": "boolean",
                                            "example": True
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/camera/zoomout": {
            "get": {
                "tags": [
                    "Camera"
                ],
                "summary": "Zoom out the camera",
                "operationId": "zoomCameraOut",
                "responses": {
                    "200": {
                        "description": "Camera zoomed out successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {
                                            "type": "boolean",
                                            "example": True
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/camera/focusin": {
            "get": {
                "tags": [
                    "Camera"
                ],
                "summary": "Focus in the camera",
                "operationId": "focusCameraIn",
                "responses": {
                    "200": {
                        "description": "Camera focused in successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {
                                            "type": "boolean",
                                            "example": True
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/camera/focusout": {
            "get": {
                "tags": [
                    "Camera"
                ],
                "summary": "Focus out the camera",
                "operationId": "focusCameraOut",
                "responses": {
                    "200": {
                        "description": "Camera focused out successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {
                                            "type": "boolean",
                                            "example": True
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/camera/autofocus": {
            "get": {
                "tags": [
                    "Camera"
                ],
                "summary": "Auto-focus the camera",
                "operationId": "autoFocusCamera",
                "responses": {
                    "200": {
                        "description": "Camera auto-focused successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {
                                            "type": "boolean",
                                            "example": True
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/export/prometheus/metrics": {
            "get": {
                "tags": [
                    "Informations"
                ],
                "summary": "Fetch Prometheus metrics",
                "operationId": "getPrometheusMetrics",
                "responses": {
                    "200": {
                        "description": "Successfully retrieved Prometheus metrics",
                        "content": {
                            "text/plain": {
                                "schema": {
                                    "type": "string",
                                    "example": "# TYPE pikvm_atx_enabled gauge\npikvm_atx_enabled 1\n# TYPE pikvm_atx_power gauge\npikvm_atx_power 1\n# TYPE pikvm_gpio_online_0 gauge\npikvm_gpio_online_0 1\n# TYPE pikvm_fan gauge\npikvm_fan 0\n"
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Error retrieving Prometheus metrics",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "An error occurred while fetching the metrics"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/flash_ifwi": {
            "get": {
                "tags": [
                    "Firmware"
                ],
                "summary": "Flash IFWI firmware",
                "operationId": "flashIfwi",
                "parameters": [
                    {
                        "name": "ifwi_file",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "example": "/path/to/firmware/file.ifwi"
                        },
                        "description": "The path to the IFWI firmware file to flash."
                    }
                ],
                "responses": {
                    "200": {
                        "description": "IFWI flashing operation was successful",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {
                                            "type": "string",
                                            "example": "Operation successful"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad request, invalid firmware file",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "Firmware file /path/to/firmware/file.ifwi does not exist."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Server error during the flashing process",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "Error flashing firmware: [error message]"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/flash-os": {
            "post": {
                "tags": [
                    "EDK"
                ],
                "summary": "Flash OS Command",
                "operationId": "flashOs",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "order": {
                                        "type": "string",
                                        "example": "1",
                                        "description": "The order of the boot configuration."
                                    }
                                },
                                "required": [
                                    "order"
                                ]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Command processed successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {
                                            "type": "string",
                                            "example": "Command processed success"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad request due to invalid input",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "No order provided"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Server error during serial operation",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "Failed to open serial connection"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/bin-files": {
            "get": {
                "tags": [
                    "Firmware"
                ],
                "summary": "Retrieve .bin files",
                "responses": {
                    "200": {
                        "description": "List of .bin files",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "string"
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/hid/system_state": {
            "get": {
                "tags": [
                    "Hid events"
                ],
                "summary": "Get the system state.",
                "operationId": "getSystemState",
                "responses": {
                    "200": {
                        "description": "Successful response with system state.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "input_status_binary": {
                                            "type": "string",
                                            "description": "Binary representation of the input status."
                                        },
                                        "input_status_hexadecimal": {
                                            "type": "string",
                                            "description": "Hexadecimal representation of the input status."
                                        }
                                    },
                                    "required": [
                                        "input_status_binary",
                                        "input_status_hexadecimal"
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        },
        "/hid": {
            "get": {
                "tags": [
                    "Hid events"
                ],
                "summary": "Get the current HID state.",
                "operationId": "getHidState",
                "responses": {
                    "200": {
                        "description": "Successful response with HID state.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": True
                                }
                            }
                        }
                    }
                }
            }
        },
        "/hid/set_params": {
            "post": {
                "tags": [
                    "Hid events"
                ],
                "summary": "Set parameters for HID.",
                "operationId": "setHidParams",
                "parameters": [
                    {
                        "name": "keyboard_output",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string"
                        }
                    },
                    {
                        "name": "mouse_output",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string"
                        }
                    },
                    {
                        "name": "jiggler",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "boolean"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Parameters set successfully.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/hid/set_connected": {
            "post": {
                "tags": [
                    "Hid events"
                ],
                "summary": "Set the connected state of HID.",
                "operationId": "setHidConnected",
                "parameters": [
                    {
                        "name": "connected",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "boolean"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Connected state set successfully.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/hid/reset": {
            "post": {
                "tags": [
                    "Hid events"
                ],
                "summary": "Reset HID state.",
                "operationId": "resetHid",
                "responses": {
                    "200": {
                        "description": "HID reset successfully.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/hid/keymaps": {
            "get": {
                "tags": [
                    "Hid events"
                ],
                "summary": "Get available keymaps.",
                "operationId": "getKeymaps",
                "responses": {
                    "200": {
                        "description": "Successful response with keymaps.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "keymaps": {
                                            "type": "object",
                                            "properties": {
                                                "default": {
                                                    "type": "string",
                                                    "description": "The default keymap name."
                                                },
                                                "available": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "string"
                                                    },
                                                    "description": "List of available keymaps."
                                                }
                                            },
                                            "required": [
                                                "default",
                                                "available"
                                            ]
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/hid/print": {
            "post": {
                "tags": [
                    "Hid events"
                ],
                "summary": "Send text to be printed via HID.",
                "operationId": "printText",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "description": "Limit the number of characters to print."
                        }
                    },
                    {
                        "name": "keymap",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "description": "Specify the keymap to use."
                        }
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "text/plain": {
                            "schema": {
                                "type": "string",
                                "description": "Text to be printed."
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Text sent for printing successfully.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/postcode/get_data": {
            "get": {
                "tags": [
                    "Postcode"
                ],
                "summary": "Get data from postcodes.",
                "operationId": "getPostcodeData",
                "parameters": [
                    {
                        "name": "lastline",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "description": "Specify the line number to get data from."
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful response with postcode data.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "Linenumber": {
                                            "type": "integer",
                                            "description": "The line number of the last occurrence."
                                        },
                                        "hexdata": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            },
                                            "description": "Hexadecimal data from the log."
                                        }
                                    },
                                    "required": [
                                        "Linenumber",
                                        "hexdata"
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        },
        "/postcode/get_logs": {
            "get": {
                "tags": [
                    "Postcode"
                ],
                "summary": "Get logs from postcodes.",
                "operationId": "getPostcodeLogs",
                "responses": {
                    "200": {
                        "description": "Successful response with logs.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "Logs": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            },
                                            "description": "List of logs."
                                        }
                                    },
                                    "required": [
                                        "Logs"
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        },
        "/hid/events/send_key": {
            "post": {
                "tags": [
                    "Hid events"
                ],
                "summary": "Send a key event via HID.",
                "operationId": "sendHidKeyEvent",
                "parameters": [
                    {
                        "name": "key",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string"
                        }
                    },
                    {
                        "name": "state",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "boolean"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Key event sent successfully.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/hid/events/send_mouse_button": {
            "post": {
                "tags": [
                    "Hid events"
                ],
                "summary": "Send a mouse button event via HID.",
                "operationId": "sendHidMouseButtonEvent",
                "parameters": [
                    {
                        "name": "button",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string"
                        }
                    },
                    {
                        "name": "state",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "boolean"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Mouse button event sent successfully.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/hid/events/send_mouse_move": {
            "post": {
                "tags": [
                    "Hid events"
                ],
                "summary": "Send a mouse move event via HID.",
                "operationId": "sendHidMouseMoveEvent",
                "parameters": [
                    {
                        "name": "x",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "integer"
                        }
                    },
                    {
                        "name": "y",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "integer"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Mouse move event sent successfully.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/info": {
            "get": {
                "tags": [
                    "Informations"
                ],
                "summary": "Get system information",
                "operationId": "getInfo",
                "parameters": [
                    {
                        "name": "fields",
                        "in": "query",
                        "description": "Comma-separated list of fields to retrieve",
                        "required": False,
                        "schema": {
                            "type": "string"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": {
                                        "type": "string"
                                    }
                                },
                                "example": {
                                    "gpio_state": "active",
                                    "hid_state": "ready"
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid query parameters"
                    }
                }
            }
        },
        "/info2": {
            "get": {
                "tags": [
                    "Informations"
                ],
                "summary": "Get system information from InfoManager2",
                "operationId": "getInfo2",
                "parameters": [
                    {
                        "name": "fields",
                        "in": "query",
                        "description": "Comma-separated list of fields to retrieve",
                        "required": False,
                        "schema": {
                            "type": "string"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": {
                                        "type": "string"
                                    }
                                },
                                "example": {
                                    "field1": "value1",
                                    "field2": "value2"
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid query parameters"
                    }
                }
            }
        },
        "/info3": {
            "get": {
                "tags": [
                    "Informations"
                ],
                "summary": "Get system information from InfoManager3",
                "operationId": "getInfo3",
                "parameters": [
                    {
                        "name": "fields",
                        "in": "query",
                        "description": "Comma-separated list of fields to retrieve",
                        "required": False,
                        "schema": {
                            "type": "string"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": {
                                        "type": "string"
                                    }
                                },
                                "example": {
                                    "field3": "value3",
                                    "field4": "value4"
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid query parameters"
                    }
                }
            }
        },
        "/info4": {
            "get": {
                "tags": [
                    "Informations"
                ],
                "summary": "Get system information from InfoManager4",
                "operationId": "getInfo4",
                "parameters": [
                    {
                        "name": "fields",
                        "in": "query",
                        "description": "Comma-separated list of fields to retrieve",
                        "required": False,
                        "schema": {
                            "type": "string"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": {
                                        "type": "string"
                                    }
                                },
                                "example": {
                                    "field5": "value5",
                                    "field6": "value6"
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid query parameters"
                    }
                }
            }
        },
        "/current-interface": {
            "get": {
                "tags": [
                    "Interface"
                ],
                "summary": "Get the current USB interface",
                "operationId": "getCurrentInterface",
                "responses": {
                    "200": {
                        "description": "The current USB interface (ACM or NCM)",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "current_interface": {
                                            "type": "string",
                                            "description": "The current USB interface",
                                            "example": "ACM (Serial)"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Error determining the current USB interface"
                    }
                }
            }
        },
        "/enable_acm": {
            "post": {
                "tags": [
                    "Interface"
                ],
                "summary": "Enable Serial Interface",
                "operationId": "enableAcm",
                "responses": {
                    "200": {
                        "description": "ACM mode enabled successfully.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "success"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "ACM mode enabled successfully."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Error occurred while enabling ACM mode.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "error"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Command failed: <error message>"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/enable_ncm": {
            "post": {
                "tags": [
                    "Interface"
                ],
                "summary": "Enable Ethernet Interface",
                "operationId": "enableNcm",
                "responses": {
                    "200": {
                        "description": "NCM mode enabled successfully.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "success"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "NCM mode enabled successfully."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Error occurred while enabling NCM mode.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "error"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Command failed: <error message>"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/serial": {
            "post": {
                "tags": [
                    "Interface"
                ],
                "summary": "Handle serial command",
                "operationId": "handleSerialRequest",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "cmd": {
                                        "type": "string",
                                        "description": "Command to send to the serial device."
                                    }
                                },
                                "required": [
                                    "cmd"
                                ]
                            },
                            "example": {
                                "cmd": "YOUR_COMMAND_HERE"
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Command processed successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {
                                            "type": "string",
                                            "example": "Command processed successfully"
                                        },
                                        "response": {
                                            "type": "string",
                                            "description": "Response from the serial device."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "No command provided",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "No command provided"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "Failed to open serial connection"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/ethernet": {
            "get": {
                "tags": [
                    "Interface"
                ],
                "summary": "Handle ethernet command",
                "operationId": "ethernetUsb",
                "parameters": [
                    {
                        "name": "reqcmd",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "description": "Command to send over UDP. Must not be 'SYNC'."
                        },
                        "examples": {
                            "example1": {
                                "value": "YOUR_COMMAND_HERE",
                                "description": "A valid command to send."
                            }
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Command sent successfully, response received",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "stdout": {
                                            "type": "string",
                                            "description": "Response from the UDP handler."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid command or missing parameters",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string",
                                            "example": "No command provided or SYNC message ignored"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/log": {
            "get": {
                "tags": [
                    "Streamer"
                ],
                "summary": "Stream system logs",
                "operationId": "streamLogs",
                "parameters": [
                    {
                        "name": "seek",
                        "in": "query",
                        "description": "Log position to seek to",
                        "schema": {
                            "type": "integer",
                            "default": 0
                        }
                    },
                    {
                        "name": "follow",
                        "in": "query",
                        "description": "Whether to follow the log in real time",
                        "schema": {
                            "type": "boolean",
                            "default": False
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Stream of log records",
                        "content": {
                            "text/plain": {
                                "schema": {
                                    "type": "string",
                                    "description": "Log records in plain text"
                                }
                            }
                        }
                    },
                    "404": {
                        "description": "LogReader is disabled"
                    }
                }
            }
        },
        "/msd": {
            "get": {
                "tags": [
                    "Mass storage"
                ],
                "summary": "Get MSD state",
                "operationId": "getMsdState",
                "responses": {
                    "200": {
                        "description": "Successful response with MSD state",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": True
                                }
                            }
                        }
                    }
                }
            }
        },
        "/msd/set_params": {
            "post": {
                "tags": [
                    "Mass storage"
                ],
                "summary": "Set parameters for MSD",
                "operationId": "setMsdParams",
                "parameters": [
                    {
                        "name": "image",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "description": "Name of the image file"
                        }
                    },
                    {
                        "name": "cdrom",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "boolean",
                            "description": "Indicate if MSD should be treated as a CD-ROM"
                        }
                    },
                    {
                        "name": "rw",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "boolean",
                            "description": "Indicate if MSD should be read/write"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Parameters set successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/msd/set_connected": {
            "post": {
                "tags": [
                    "Mass storage"
                ],
                "summary": "Set MSD connected state",
                "operationId": "setMsdConnected",
                "parameters": [
                    {
                        "name": "connected",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "boolean",
                            "description": "Connection status of MSD"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "MSD connection state set successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/msd/read": {
            "get": {
                "tags": [
                    "Mass storage"
                ],
                "summary": "Read data from MSD",
                "operationId": "readMsdData",
                "parameters": [
                    {
                        "name": "image",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "description": "Name of the image file"
                        }
                    },
                    {
                        "name": "compress",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "none",
                                "lzma",
                                "zstd"
                            ],
                            "description": "Compression mode"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "MSD data read successfully",
                        "content": {
                            "application/octet-stream": {
                                "schema": {
                                    "type": "string",
                                    "format": "binary"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/msd/write": {
            "post": {
                "tags": [
                    "Mass storage"
                ],
                "summary": "Write data to MSD",
                "operationId": "writeMsdData",
                "parameters": [
                    {
                        "name": "prefix",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "description": "Prefix for the file name"
                        }
                    },
                    {
                        "name": "image",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "description": "Name of the image file"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "MSD data written successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "image": {
                                            "type": "object",
                                            "properties": {
                                                "name": {
                                                    "type": "string",
                                                    "description": "Name of the image"
                                                },
                                                "size": {
                                                    "type": "integer",
                                                    "description": "Size of the image"
                                                },
                                                "written": {
                                                    "type": "integer",
                                                    "description": "Amount of data written"
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/msd/write_remote": {
            "post": {
                "tags": [
                    "Mass storage"
                ],
                "summary": "Write remote data to MSD",
                "operationId": "writeRemoteMsdData",
                "parameters": [
                    {
                        "name": "prefix",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "description": "Prefix for the file name"
                        }
                    },
                    {
                        "name": "url",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "description": "URL of the remote file"
                        }
                    },
                    {
                        "name": "insecure",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "boolean",
                            "description": "Allow insecure connection"
                        }
                    },
                    {
                        "name": "timeout",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "number",
                            "description": "Timeout for the download"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Remote MSD data written successfully",
                        "content": {
                            "application/x-ndjson": {
                                "schema": {
                                    "type": "object"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/msd/remove": {
            "post": {
                "tags": [
                    "Mass storage"
                ],
                "summary": "Remove MSD image",
                "operationId": "removeMsdImage",
                "parameters": [
                    {
                        "name": "image",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "description": "Name of the image file to remove"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "MSD image removed successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/msd/reset": {
            "post": {
                "tags": [
                    "Mass storage"
                ],
                "summary": "Reset MSD",
                "operationId": "resetMsd",
                "responses": {
                    "200": {
                        "description": "MSD reset successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/redfish/v1": {
            "get": {
                "tags": [
                    "BMC"
                ],
                "summary": "Get the root Redfish service information",
                "operationId": "getRootService",
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "@odata.id": {
                                            "type": "string",
                                            "example": "/redfish/v1"
                                        },
                                        "@odata.type": {
                                            "type": "string",
                                            "example": "#ServiceRoot.v1_6_0.ServiceRoot"
                                        },
                                        "Id": {
                                            "type": "string",
                                            "example": "RootService"
                                        },
                                        "Name": {
                                            "type": "string",
                                            "example": "Root Service"
                                        },
                                        "RedfishVersion": {
                                            "type": "string",
                                            "example": "1.6.0"
                                        },
                                        "Systems": {
                                            "type": "string",
                                            "example": "/redfish/v1/Systems"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/redfish/v1/Systems": {
            "get": {
                "tags": [
                    "BMC"
                ],
                "summary": "Get the collection of systems",
                "operationId": "getSystemsCollection",
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "@odata.id": {
                                            "type": "string",
                                            "example": "/redfish/v1/Systems"
                                        },
                                        "@odata.type": {
                                            "type": "string",
                                            "example": "#ComputerSystemCollection.ComputerSystemCollection"
                                        },
                                        "Members": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "@odata.id": {
                                                        "type": "string",
                                                        "example": "/redfish/v1/Systems/0"
                                                    }
                                                }
                                            }
                                        },
                                        "Members@odata.count": {
                                            "type": "integer",
                                            "example": 1
                                        },
                                        "Name": {
                                            "type": "string",
                                            "example": "Computer System Collection"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/redfish/v1/Systems/0": {
            "get": {
                "tags": [
                    "BMC"
                ],
                "summary": "Get a specific system",
                "operationId": "getSystem",
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "@odata.id": {
                                            "type": "string",
                                            "example": "/redfish/v1/Systems/0"
                                        },
                                        "@odata.type": {
                                            "type": "string",
                                            "example": "#ComputerSystem.v1_10_0.ComputerSystem"
                                        },
                                        "Actions": {
                                            "type": "object",
                                            "properties": {
                                                "#ComputerSystem.Reset": {
                                                    "type": "object",
                                                    "properties": {
                                                        "ResetType@Redfish.AllowableValues": {
                                                            "type": "array",
                                                            "items": {
                                                                "type": "string",
                                                                "enum": [
                                                                    "On",
                                                                    "ForceOff",
                                                                    "GracefulShutdown",
                                                                    "ForceRestart",
                                                                    "ForceOn",
                                                                    "PushPowerButton"
                                                                ]
                                                            }
                                                        },
                                                        "target": {
                                                            "type": "string",
                                                            "example": "/redfish/v1/Systems/0/Actions/ComputerSystem.Reset"
                                                        }
                                                    }
                                                }
                                            }
                                        },
                                        "Id": {
                                            "type": "string",
                                            "example": "0"
                                        },
                                        "HostName": {
                                            "type": "string",
                                            "example": "example-host"
                                        },
                                        "PowerState": {
                                            "type": "string",
                                            "example": "On"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/redfish/v1/Systems/0/Actions/ComputerSystem.Reset": {
            "post": {
                "tags": [
                    "BMC"
                ],
                "summary": "Reset a specific system",
                "operationId": "resetSystem",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "ResetType": {
                                        "type": "string",
                                        "enum": [
                                            "On",
                                            "ForceOff",
                                            "GracefulShutdown",
                                            "ForceRestart",
                                            "ForceOn",
                                            "PushPowerButton"
                                        ]
                                    }
                                },
                                "required": [
                                    "ResetType"
                                ]
                            }
                        }
                    }
                },
                "responses": {
                    "204": {
                        "description": "Successful request, no content"
                    },
                    "400": {
                        "description": "Bad request, missing ResetType"
                    }
                }
            }
        },
        "/pci_enumerate_device": {
            "get": {
                "tags": [
                    "PCI_Testcase"
                ],
                "summary": "Enumerate PCI devices",
                "parameters": [
                    {
                        "name": "os",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "windows",
                                "linux",
                                "edk"
                            ]
                        }
                    },
                    {
                        "name": "location",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "host",
                                "target"
                            ]
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful enumeration of PCI devices",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": True
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request - Invalid parameters",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/pci_description_filter": {
            "get": {
                "tags": [
                    "PCI_Testcase"
                ],
                "summary": "Retrieve PCI device information filtered by description",
                "parameters": [
                    {
                        "name": "os",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "windows",
                                "linux"
                            ]
                        }
                    },
                    {
                        "name": "location",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "host",
                                "target"
                            ]
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful retrieval of PCI device information",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": True
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request - Invalid parameters",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/pci_check_driver_info": {
            "get": {
                "tags": [
                    "PCI_Testcase"
                ],
                "summary": "Check driver information",
                "parameters": [
                    {
                        "name": "os",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "windows",
                                "linux"
                            ]
                        }
                    },
                    {
                        "name": "location",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "host",
                                "target"
                            ]
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful retrieval of driver information",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": True
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request - Invalid parameters",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/pci_error_handling": {
            "get": {
                "tags": [
                    "PCI_Testcase"
                ],
                "summary": "Detect and handle PCIe errors",
                "parameters": [
                    {
                        "name": "os",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "windows",
                                "linux"
                            ]
                        }
                    },
                    {
                        "name": "location",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "host",
                                "target"
                            ]
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful error detection",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": True
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request - Invalid parameters",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/pci_power_management": {
            "get": {
                "tags": [
                    "PCI_Testcase"
                ],
                "summary": "Check PCIe power management",
                "parameters": [
                    {
                        "name": "os",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "windows",
                                "linux"
                            ]
                        }
                    },
                    {
                        "name": "location",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "host",
                                "target"
                            ]
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful retrieval of power management info",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": True
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request - Invalid parameters",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/pci_memory_info": {
            "get": {
                "tags": [
                    "PCI_Testcase"
                ],
                "summary": "Retrieve memory information",
                "parameters": [
                    {
                        "name": "os",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "windows",
                                "linux"
                            ]
                        }
                    },
                    {
                        "name": "location",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "host",
                                "target"
                            ]
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful retrieval of memory information",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": True
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request - Invalid parameters",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/pci_baseboard_info": {
            "get": {
                "tags": [
                    "PCI_Testcase"
                ],
                "summary": "Retrieve baseboard (motherboard) information",
                "parameters": [
                    {
                        "name": "os",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "windows",
                                "linux"
                            ]
                        }
                    },
                    {
                        "name": "location",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "host",
                                "target"
                            ]
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful retrieval of baseboard information",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": True
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request - Invalid parameters",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/pci_check_configuration_space": {
            "get": {
                "tags": [
                    "PCI_Testcase"
                ],
                "summary": "Retrieve the configuration space of Bus 0, Device 0, Function 0",
                "parameters": [
                    {
                        "name": "os",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "edk"
                            ]
                        }
                    },
                    {
                        "name": "location",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "target"
                            ]
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful retrieval of configuration space",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": True
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request - Invalid parameters",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/pci_check_configuration_space_segment": {
            "get": {
                "tags": [
                    "PCI_Testcase"
                ],
                "summary": "Retrieve the configuration space of Segment 0, Bus 0, Device 0, Function 0",
                "parameters": [
                    {
                        "name": "os",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "edk"
                            ]
                        }
                    },
                    {
                        "name": "location",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": [
                                "target"
                            ]
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful retrieval of configuration space segment",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": True
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request - Invalid parameters",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
         "/enumerate_usb_device": {
      "get": {
          "tags":[
            "USB_Testcase"  
          ],
        "summary": "Enumerate USB Devices",
        "description": "Enumerate USB devices based on the OS over serial connection. Only applicable for 'target' location.",
        "parameters": [
          {
            "name": "location",
            "in": "query",
            "description": "Location of the device (e.g., 'target').",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          },
          {
            "name": "os",
            "in": "query",
            "description": "Operating system of the device (e.g., 'windows', 'linux', 'edk').",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux", "edk"],
              "default": "windows"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful enumeration of USB devices",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "message": { "type": "string" },
                    "response": { "type": "string" },
                    "error": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid request or location not applicable"
          }
        }
      }
    },
    "/usb_description_filter": {
      "get": {
          "tags":[
            "USB_Testcase"  
          ],
        "summary": "USB Description Filter",
        "description": "Retrieve USB device information filtered by description (e.g., '%USB%') over serial. Only applicable for 'target' location.",
        "parameters": [
          {
            "name": "location",
            "in": "query",
            "description": "Location of the device (e.g., 'target').",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          },
          {
            "name": "os",
            "in": "query",
            "description": "Operating system of the device (e.g., 'windows', 'linux').",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "USB device information retrieved",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "message": { "type": "string" },
                    "response": { "type": "string" },
                    "error": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid request or location not applicable"
          }
        }
      }
    },
    "/check_usb_driver_info": {
      "get": {
          "tags":[
            "USB_Testcase"  
          ],
        "summary": "Check USB Driver Info",
        "description": "Check USB driver information over serial connection. Only applicable for 'target' location.",
        "parameters": [
          {
            "name": "location",
            "in": "query",
            "description": "Location of the device (e.g., 'target').",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          },
          {
            "name": "os",
            "in": "query",
            "description": "Operating system of the device (e.g., 'windows', 'linux').",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "USB driver information retrieved",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "message": { "type": "string" },
                    "response": { "type": "string" },
                    "error": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid request or location not applicable"
          }
        }
      }
    },
    "/usb_error_handling": {
      "get": {
          "tags":[
            "USB_Testcase"  
          ],
        "summary": "USB Error Handling",
        "description": "Detect and handle USB errors over serial connection. Only applicable for 'target' location.",
        "parameters": [
          {
            "name": "location",
            "in": "query",
            "description": "Location of the device (e.g., 'target').",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          },
          {
            "name": "os",
            "in": "query",
            "description": "Operating system of the device (e.g., 'windows', 'linux').",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "USB error information handled",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "message": { "type": "string" },
                    "response": { "type": "string" },
                    "error": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid request or location not applicable"
          }
        }
      }
    },
    "/usb_power_management": {
      "get": {
          "tags":[
            "USB_Testcase"  
          ],
        "summary": "USB Power Management",
        "description": "Check USB power management over serial connection. Only applicable for 'target' location.",
        "parameters": [
          {
            "name": "location",
            "in": "query",
            "description": "Location of the device (e.g., 'target').",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          },
          {
            "name": "os",
            "in": "query",
            "description": "Operating system of the device (e.g., 'windows', 'linux').",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "USB power management information retrieved",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "message": { "type": "string" },
                    "response": { "type": "string" },
                    "error": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid request or location not applicable"
          }
        }
      }
    },
    "/enumerate_bluetooth_device": {
      "get": {
          "tags":[
            "Bluetooth_Testcase"  
          ],
        "summary": "Enumerate Bluetooth devices",
        "operationId": "enumerateBluetoothDevice",
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "required": False,
            "description": "Operating system (windows, linux, edk)",
            "schema": {
              "type": "string",
              "enum": [
                "windows",
                "linux",
                "edk"
              ],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "required": False,
            "description": "Location of the device (host or target)",
            "schema": {
              "type": "string",
              "enum": [
                "host",
                "target"
              ],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Device enumeration successful",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "message": {
                      "type": "string"
                    },
                    "response": {
                      "type": "string"
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "description": "Error message"
                    }
                  }
                }
              }
            }
          }
        }
      }
    },
    "/bluetooth_driver_information": {
      "get": {
          "tags":[
            "Bluetooth_Testcase"  
          ],
        "summary": "Retrieve Bluetooth driver information",
        "operationId": "bluetoothDriverInformation",
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "required": False,
            "description": "Operating system (windows, linux)",
            "schema": {
              "type": "string",
              "enum": [
                "windows",
                "linux"
              ],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "required": False,
            "description": "Location of the device (host or target)",
            "schema": {
              "type": "string",
              "enum": [
                "host",
                "target"
              ],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Driver information retrieved successfully",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "message": {
                      "type": "string"
                    },
                    "response": {
                      "type": "string"
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "description": "Error message"
                    }
                  }
                }
              }
            }
          }
        }
      }
    },
    "/check_bluetooth_status": {
      "get": {
          "tags":[
            "Bluetooth_Testcase"  
          ],
        "summary": "Check Bluetooth status",
        "operationId": "checkBluetoothStatus",
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "required": False,
            "description": "Operating system (windows, linux)",
            "schema": {
              "type": "string",
              "enum": [
                "windows",
                "linux"
              ],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "required": False,
            "description": "Location of the device (host or target)",
            "schema": {
              "type": "string",
              "enum": [
                "host",
                "target"
              ],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Bluetooth status checked successfully",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "message": {
                      "type": "string"
                    },
                    "response": {
                      "type": "string"
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "description": "Error message"
                    }
                  }
                }
              }
            }
          }
        }
      }
    },
    "/bluetooth_error_handling": {
      "get": {
          "tags":[
            "Bluetooth_Testcase"  
          ],
        "summary": "Detect and handle Bluetooth errors",
        "operationId": "bluetoothErrorHandling",
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "required": False,
            "description": "Operating system (windows, linux)",
            "schema": {
              "type": "string",
              "enum": [
                "windows",
                "linux"
              ],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "required": False,
            "description": "Location of the device (host or target)",
            "schema": {
              "type": "string",
              "enum": [
                "host",
                "target"
              ],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Bluetooth error handling completed successfully",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "message": {
                      "type": "string"
                    },
                    "response": {
                      "type": "string"
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "description": "Error message"
                    }
                  }
                }
              }
            }
          }
        }
      }
    },
    "/bluetooth_power_management": {
      "get": {
          "tags":[
            "Bluetooth_Testcase"  
          ],
        "summary": "Check Bluetooth power management",
        "operationId": "bluetoothPowerManagement",
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "required": False,
            "description": "Operating system (windows, linux)",
            "schema": {
              "type": "string",
              "enum": [
                "windows",
                "linux"
              ],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "required": False,
            "description": "Location of the device (host or target)",
            "schema": {
              "type": "string",
              "enum": [
                "host",
                "target"
              ],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Bluetooth power management checked successfully",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "message": {
                      "type": "string"
                    },
                    "response": {
                      "type": "string"
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "description": "Error message"
                    }
                  }
                }
              }
            }
          }
        }
      }
    },
    "/wifi_adapter_information": {
      "get": {
          "tags":[
            "WiFi_Testcase"  
          ],
        "summary": "Retrieve Wi-Fi Adapter Information",
        "operationId": "wifiAdapterInformation",
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "description": "Operating system (windows or linux)",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "description": "Location of the device (host or target)",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved Wi-Fi adapter information",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string"
                    },
                    "adapter_info": {
                      "type": "object",
                      "properties": {
                        "Name": { "type": "string" },
                        "Manufacturer": { "type": "string" },
                        "NetConnectionID": { "type": "string" },
                        "Speed": { "type": "string" },
                        "MACAddress": { "type": "string" }
                      }
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters provided"
          }
        }
      }
    },
    "/wifi_adapter_driver_info": {
      "get": {
          "tags":[
            "WiFi_Testcase"  
          ],
        "summary": "Retrieve Wi-Fi Adapter Driver Information",
        "operationId": "wifiAdapterDriverInfo",
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "description": "Operating system (windows or linux)",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "description": "Location of the device (host or target)",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved Wi-Fi adapter driver information",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string"
                    },
                    "driver_info": {
                      "type": "object",
                      "properties": {
                        "DeviceName": { "type": "string" },
                        "DriverVersion": { "type": "string" },
                        "Manufacturer": { "type": "string" },
                        "DriverDate": { "type": "string" }
                      }
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters provided"
          }
        }
      }
    },
    "/wifi_adapter_status": {
      "get": {
          "tags":[
            "WiFi_Testcase"  
          ],
        "summary": "Check Wi-Fi Adapter Status",
        "operationId": "wifiAdapterStatus",
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "description": "Operating system (windows or linux)",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "description": "Location of the device (host or target)",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved Wi-Fi adapter status",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string"
                    },
                    "status": {
                      "type": "object",
                      "properties": {
                        "NetConnectionStatus": { "type": "integer" },
                        "Name": { "type": "string" }
                      }
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters provided"
          }
        }
      }
    },
    "/wifi_ip_configuration": {
      "get": {
          "tags":[
            "WiFi_Testcase"  
          ],
        "summary": "Retrieve Wi-Fi Adapter IP Configuration",
        "operationId": "wifiIpConfiguration",
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "description": "Operating system (windows or linux)",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "description": "Location of the device (host or target)",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved Wi-Fi adapter IP configuration",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string"
                    },
                    "ip_config": {
                      "type": "object",
                      "properties": {
                        "Description": { "type": "string" },
                        "IPAddress": { "type": "array", "items": { "type": "string" } },
                        "IPSubnet": { "type": "array", "items": { "type": "string" } },
                        "DefaultIPGateway": { "type": "array", "items": { "type": "string" } }
                      }
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters provided"
          }
        }
      }
    },
    "/wifi_power_management": {
      "get": {
          "tags":[
            "WiFi_Testcase"  
          ],
        "summary": "Retrieve Wi-Fi Power Management Information",
        "operationId": "wifiPowerManagement",
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "description": "Operating system (windows or linux)",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "description": "Location of the device (host or target)",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved Wi-Fi power management information",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string"
                    },
                    "power_management": {
                      "type": "object",
                      "properties": {
                        "PowerManagementSupported": { "type": "boolean" },
                        "PowerManagementCapabilities": { "type": "array", "items": { "type": "integer" } }
                      }
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters provided"
          }
        }
      }
    },
    "/wifi_mac_address": {
      "get": {
          "tags":[
            "WiFi_Testcase"  
          ],
        "summary": "Retrieve Wi-Fi MAC Address",
        "operationId": "wifiMacAddress",
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "description": "Operating system (windows or linux)",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "description": "Location of the device (host or target)",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved Wi-Fi MAC address",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string"
                    },
                    "mac_address": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters provided"
          }
        }
      }
    },
    "/lan_adapter_information": {
      "get": {
        "tags": ["LAN_Testcase"],
        "summary": "Retrieve LAN adapter information",
        "parameters": [
          {
            "name": "interface",
            "in": "query",
            "description": "Network interface to query",
            "required": False,
            "schema": {
              "type": "string",
              "default": "enp1s0"
            }
          },
          {
            "name": "os",
            "in": "query",
            "description": "Operating system ('windows', 'linux', 'edk')",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux", "edk"],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "description": "Execution location ('host' or 'target')",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved LAN adapter information",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": { "type": "string" },
                    "message": { "type": "string" },
                    "response": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters provided"
          }
        }
      }
    },
    "/lan_adapter_driver_info": {
      "get": {
        "tags": ["LAN_Testcase"],
        "summary": "Retrieve LAN adapter driver information",
        "parameters": [
          {
            "name": "interface",
            "in": "query",
            "description": "Network interface to query",
            "required": False,
            "schema": {
              "type": "string",
              "default": "enp1s0"
            }
          },
          {
            "name": "os",
            "in": "query",
            "description": "Operating system ('windows', 'linux')",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "description": "Execution location ('host' or 'target')",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved LAN adapter driver information",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": { "type": "string" },
                    "message": { "type": "string" },
                    "response": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters provided"
          }
        }
      }
    },
    "/lan_adapter_status": {
      "get": {
        "tags": ["LAN_Testcase"],
        "summary": "Check LAN adapter status",
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "description": "Operating system ('windows', 'linux')",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "description": "Execution location ('host' or 'target')",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully checked LAN adapter status",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": { "type": "string" },
                    "message": { "type": "string" },
                    "response": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters provided"
          }
        }
      }
    },
    "/lan_ip_configuration": {
      "get": {
        "tags": ["LAN_Testcase"],
        "summary": "Retrieve LAN adapter IP configuration",
        "parameters": [
          {
            "name": "interface",
            "in": "query",
            "description": "Network interface to query",
            "required": False,
            "schema": {
              "type": "string",
              "default": "enp1s0"
            }
          },
          {
            "name": "os",
            "in": "query",
            "description": "Operating system ('windows', 'linux', 'edk')",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux", "edk"],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "description": "Execution location ('host' or 'target')",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved LAN adapter IP configuration",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": { "type": "string" },
                    "message": { "type": "string" },
                    "response": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters provided"
          }
        }
      }
    },
    "/lan_power_management": {
      "get": {
        "tags": ["LAN_Testcase"],
        "summary": "Retrieve LAN power management information",
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "description": "Operating system ('windows', 'linux')",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "description": "Execution location ('host' or 'target')",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved LAN power management information",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": { "type": "string" },
                    "message": { "type": "string" },
                    "response": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters provided"
          }
        }
      }
    },
    "/lan_mac_address": {
      "get": {
        "tags": ["LAN_Testcase"],
        "summary": "Retrieve LAN MAC address",
        "parameters": [
          {
            "name": "interface",
            "in": "query",
            "description": "Network interface to query",
            "required": False,
            "schema": {
              "type": "string",
              "default": "enp1s0"
            }
          },
          {
            "name": "os",
            "in": "query",
            "description": "Operating system ('windows', 'linux')",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            }
          },
          {
            "name": "location",
            "in": "query",
            "description": "Execution location ('host' or 'target')",
            "required": False,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved LAN MAC address",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": { "type": "string" },
                    "message": { "type": "string" },
                    "response": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Invalid parameters provided"
          }
        }
      }
    },
     "/check_cpu_status": {
      "get": {
        "summary": "Check CPU Status",
        "description": "Fetches CPU load and status.",
        "tags": ["RAS_Testcase"],
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux", "edk"],
              "default": "windows"
            },
            "description": "Operating system (windows, linux, edk)"
          },
          {
            "name": "location",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            },
            "description": "Location of the system (host or target)"
          }
        ],
        "responses": {
          "200": {
            "description": "CPU status data",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": { "type": "string" },
                    "message": { "type": "string" },
                    "response": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": { "description": "Invalid parameters provided" }
        }
      }
    },
    "/check_fan_status": {
      "get": {
        "summary": "Check Fan Status",
        "description": "Fetches fan speed and status.",
        "tags": ["RAS_Testcase"],
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            },
            "description": "Operating system (windows, linux)"
          },
          {
            "name": "location",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            },
            "description": "Location of the system (host or target)"
          }
        ],
        "responses": {
          "200": {
            "description": "Fan status data",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": { "type": "string" },
                    "message": { "type": "string" },
                    "response": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": { "description": "Invalid parameters provided" }
        }
      }
    },
    "/check_memory_info": {
      "get": {
        "summary": "Check Memory Info",
        "description": "Fetches memory details such as capacity and speed.",
        "tags": ["RAS_Testcase"],
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux", "edk"],
              "default": "windows"
            },
            "description": "Operating system (windows, linux, edk)"
          },
          {
            "name": "location",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            },
            "description": "Location of the system (host or target)"
          }
        ],
        "responses": {
          "200": {
            "description": "Memory information data",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": { "type": "string" },
                    "message": { "type": "string" },
                    "response": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": { "description": "Invalid parameters provided" }
        }
      }
    },
    "/check_disk_status": {
      "get": {
        "summary": "Check Disk Status",
        "description": "Fetches disk drive details such as model and status.",
        "tags": ["RAS_Testcase"],
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux", "edk"],
              "default": "windows"
            },
            "description": "Operating system (windows, linux, edk)"
          },
          {
            "name": "location",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            },
            "description": "Location of the system (host or target)"
          }
        ],
        "responses": {
          "200": {
            "description": "Disk status data",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": { "type": "string" },
                    "message": { "type": "string" },
                    "response": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": { "description": "Invalid parameters provided" }
        }
      }
    },
    "/check_network_status": {
      "get": {
        "summary": "Check Network Interface Status",
        "description": "Fetches network interface details and connection status.",
        "tags": ["RAS_Testcase"],
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux", "edk"],
              "default": "windows"
            },
            "description": "Operating system (windows, linux, edk)"
          },
          {
            "name": "location",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            },
            "description": "Location of the system (host or target)"
          },
          {
            "name": "interface",
            "in": "query",
            "required": False,
            "schema": {
              "type": "string",
              "default": "enp1s0"
            },
            "description": "Network interface name (default is 'enp1s0')"
          }
        ],
        "responses": {
          "200": {
            "description": "Network status data",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": { "type": "string" },
                    "message": { "type": "string" },
                    "response": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": { "description": "Invalid parameters provided" }
        }
      }
    },
    "/check_battery_status": {
      "get": {
        "summary": "Check Battery Status",
        "description": "Fetches battery status and estimated charge remaining.",
        "tags": ["RAS_Testcase"],
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux", "edk"],
              "default": "windows"
            },
            "description": "Operating system (windows, linux, edk)"
          },
          {
            "name": "location",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            },
            "description": "Location of the system (host or target)"
          }
        ],
        "responses": {
          "200": {
            "description": "Battery status data",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": { "type": "string" },
                    "message": { "type": "string" },
                    "response": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": { "description": "Invalid parameters provided" }
        }
      }
    },
    "/check_system_events": {
      
      "get": {
        "summary": "Check System Events",
        "description": "Fetches recent system events.",
        "tags": ["RAS_Testcase"],
        "parameters": [
          {
            "name": "os",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["windows", "linux"],
              "default": "windows"
            },
            "description": "Operating system (windows, linux)"
          },
          {
            "name": "location",
            "in": "query",
            "required": True,
            "schema": {
              "type": "string",
              "enum": ["host", "target"],
              "default": "target"
            },
            "description": "Location of the system (host or target)"
          }
        ],
        "responses": {
          "200": {
            "description": "System events data",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": { "type": "string" },
                    "message": { "type": "string" },
                    "response": { "type": "string" }
                  }
                }
              }
            }
          },
          "400": { "description": "Invalid parameters provided" }
        }
      }
    }
  
    }
    }
        json_content = json.dumps(swagger_data, sort_keys=False, indent=4)

        # Use web.Response to send raw JSON
        return web.Response(text=json_content, content_type='application/json')
    


    @exposed_http("GET", "/ws")
    async def __ws_handler(self, request: Request) -> WebSocketResponse:    
        stream = valid_bool(request.query.get("stream", True))
        logger = get_logger(0)
        logger.info("Rahul Babel /ws called")
        async with self._ws_session(request, stream=stream) as ws:
            try:
                stage1 = [
                    ("gpio_model_state", await self.__user_gpio.get_model()),
                    ("hid_keymaps_state", await self.__hid_api.get_keymaps()),
                    ("streamer_ocr_state", await self.__streamer_api.get_ocr()),
                ]
                stage2 = [
                    (comp.event_type, await comp.get_state())
                    for comp in self.__components
                    if comp.get_state
                ]
                #logger.info("Stage2:", stage2)
                stages = stage1 + stage2
                events = dict(stages)  # Convert to a dictionary

                for stage in [stage1, stage2]:
                    await asyncio.gather(*[
                        ws.send_event(event_type, events[event_type])
                        for (event_type, _) in stage
                        if event_type in events
                    ])

                await ws.send_event("loop", {})
                return await self._ws_loop(ws)

            except Exception as e:
                logger.error("WebSocket handler error: %s", e)

            finally:
                # If needed, add cleanup logic here
                pass

    @exposed_ws("ping")
    async def __ws_ping_handler(self, ws: WsSession, _: Dict) -> None:
        await ws.send_event("pong", {})

    # ===== SYSTEM STUFF

    def run(self, **kwargs: Any) -> None:  # type: ignore  # pylint: disable=arguments-differ
        for comp in self.__components:
            if comp.sysprep:
                comp.sysprep()
        aioproc.rename_process("main")
        super().run(**kwargs)

    async def _check_request_auth(self, exposed: HttpExposed, request: Request) -> None:
        await check_request_auth(self.__auth_manager, exposed, request)

    async def _init_app(self) -> None:
        aiotools.create_deadly_task("Stream controller", self.__stream_controller())
        aiotools.create_deadly_task("Stream controller", self.__stream_controller2())
        aiotools.create_deadly_task("Stream controller", self.__stream_controller3())
        aiotools.create_deadly_task("Stream controller", self.__stream_controller4())        
        for comp in self.__components:
            if comp.systask:
                aiotools.create_deadly_task(comp.name, comp.systask())
            if comp.poll_state:
                aiotools.create_deadly_task(f"{comp.name} [poller]", self.__poll_state(comp.event_type, comp.poll_state()))
        aiotools.create_deadly_task("Stream snapshoter", self.__stream_snapshoter())
        self._add_exposed(*self.__apis)
        #aiotools.create_deadly_task("Stream controller2", self.__stream_controller2())
        #for comp in self.__components:
        #    if comp.systask:
        #        aiotools.create_deadly_task(comp.name, comp.systask())
        #    if comp.poll_state:
        #        aiotools.create_deadly_task(f"{comp.name} [poller]", self.__poll_state(comp.event_type, comp.poll_state()))
        # aiotools.create_deadly_task("Stream snapshoter", self.__stream_snapshoter())
        #self._add_exposed(*self.__apis)    

    async def _on_shutdown(self) -> None:
        logger = get_logger(0)
        logger.info("Waiting short tasks ...")
        await aiotools.wait_all_short_tasks()
        logger.info("Stopping system tasks ...")
        await aiotools.stop_all_deadly_tasks()
        logger.info("Disconnecting clients ...")
        await self._close_all_wss()
        logger.info("On-Shutdown complete")

    async def _on_cleanup(self) -> None:
        logger = get_logger(0)
        for comp in self.__components:
            if comp.cleanup:
                logger.info("Cleaning up %s ...", comp.name)
                try:
                    await comp.cleanup()  # type: ignore
                except Exception:
                    logger.exception("Cleanup error on %s", comp.name)
        logger.info("On-Cleanup complete")

    async def _on_ws_opened(self) -> None:
        self.__streamer_notifier.notify()
        self.__streamer_notifier2.notify()
        self.__streamer_notifier3.notify()
        self.__streamer_notifier4.notify()

    async def _on_ws_closed(self) -> None:
        self.__hid.clear_events()
        self.__streamer_notifier.notify()
        self.__streamer_notifier2.notify()
        self.__streamer_notifier3.notify()
        self.__streamer_notifier4.notify()

    def __has_stream_clients(self) -> bool:
        return bool(sum(map(
            (lambda ws: ws.kwargs["stream"]),
            self._get_wss(),
        )))

    # ===== SYSTEM TASKS

    async def __stream_controller(self) -> None:
        prev = False
        while True:
            cur = (self.__has_stream_clients() or self.__snapshoter.snapshoting() or self.__stream_forever)
            if not prev and cur:
                await self.__streamer.ensure_start(reset=False)
            elif prev and not cur:
                await self.__streamer.ensure_stop(immediately=False)

            if self.__reset_streamer or self.__new_streamer_params:
                start = self.__streamer.is_working()
                await self.__streamer.ensure_stop(immediately=True)
                if self.__new_streamer_params:
                    self.__streamer.set_params(self.__new_streamer_params)
                    self.__new_streamer_params = {}
                if start:
                    await self.__streamer.ensure_start(reset=self.__reset_streamer)
                self.__reset_streamer = False

            prev = cur
            await self.__streamer_notifier.wait()

    async def __stream_controller2(self) -> None:
        prev = False
        while True:
            cur = (self.__has_stream_clients() or self.__snapshoter.snapshoting() or self.__stream_forever2)
            if not prev and cur:
                await self.__streamer2.ensure_start(reset=False)
            elif prev and not cur:
                await self.__streamer2.ensure_stop(immediately=False)

            if self.__reset_streamer2 or self.__new_streamer_params2:
                start = self.__streamer2.is_working()
                await self.__streamer2.ensure_stop(immediately=True)
                if self.__new_streamer_params2:
                    self.__streamer2.set_params(self.__new_streamer_params2)
                    self.__new_streamer_params2 = {}
                if start:
                    await self.__streamer2.ensure_start(reset=self.__reset_streamer2)
                self.__reset_streamer2 = False

            prev = cur
            await self.__streamer_notifier2.wait()


    async def __stream_controller3(self) -> None:
        prev = False
        while True:
            cur = (self.__has_stream_clients() or self.__snapshoter.snapshoting() or self.__stream_forever3)
            if not prev and cur:
                await self.__streamer3.ensure_start(reset=False)
            elif prev and not cur:
                await self.__streamer3.ensure_stop(immediately=False)

            if self.__reset_streamer3 or self.__new_streamer_params3:
                start = self.__streamer3.is_working()
                await self.__streamer3.ensure_stop(immediately=True)
                if self.__new_streamer_params3:
                    self.__streamer3.set_params(self.__new_streamer_params3)
                    self.__new_streamer_params3 = {}
                if start:
                    await self.__streamer3.ensure_start(reset=self.__reset_streamer3)
                self.__reset_streamer3 = False

            prev = cur
            await self.__streamer_notifier3.wait()

    async def __stream_controller4(self) -> None:
        prev = False
        while True:
            cur = (self.__has_stream_clients() or self.__snapshoter.snapshoting() or self.__stream_forever4)
            if not prev and cur:
                await self.__streamer4.ensure_start(reset=False)
            elif prev and not cur:
                await self.__streamer4.ensure_stop(immediately=False)

            if self.__reset_streamer4 or self.__new_streamer_params4:
                start = self.__streamer4.is_working()
                await self.__streamer4.ensure_stop(immediately=True)
                if self.__new_streamer_params4:
                    self.__streamer4.set_params(self.__new_streamer_params4)
                    self.__new_streamer_params4 = {}
                if start:
                    await self.__streamer4.ensure_start(reset=self.__reset_streamer4)
                self.__reset_streamer4 = False

            prev = cur
            await self.__streamer_notifier4.wait()

    async def __poll_state(self, event_type: str, poller: AsyncGenerator[Dict, None]) -> None:
        async for state in poller:
            await self._broadcast_ws_event(event_type, state)

    async def __stream_snapshoter(self) -> None:
        await self.__snapshoter.run(
            is_live=self.__has_stream_clients,
            notifier=self.__streamer_notifier,
        )

    def __run_system_task(self, method: Callable, *args: Any) -> None:
        async def wrapper() -> None:
            try:
                await method(*args)
                raise RuntimeError(f"Dead system task: {method}"
                                   f"({', '.join(getattr(arg, '__name__', str(arg)) for arg in args)})")
            except asyncio.CancelledError:
                pass
            except Exception:
                get_logger().exception("Unhandled exception, killing myself ...")
                os.kill(os.getpid(), signal.SIGTERM)
        self.__system_tasks.append(asyncio.create_task(wrapper()))
