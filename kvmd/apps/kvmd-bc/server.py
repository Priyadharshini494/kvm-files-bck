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

from typing import Tuple
from typing import List
from typing import Dict
from typing import Callable
from typing import Coroutine
from typing import AsyncGenerator
from typing import Optional
from typing import Any

from aiohttp.web import Request
from aiohttp.web import Response
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
