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


from ...logging import get_logger

from ...plugins.hid import get_hid_class
from ...plugins.atx import get_atx_class
from ...plugins.msd import get_msd_class

from .. import init

from .auth import AuthManager
from .info import InfoManager
from .info import InfoManager2
from .logreader import LogReader
from .ugpio import UserGpio
from .streamer import Streamer
from .streamer2 import Streamer2
from .streamer3 import Streamer3
from .streamer4 import Streamer4
from .snapshoter import Snapshoter
from .ocr import Ocr
from .server import KvmdServer


# =====
def main(argv: (list[str] | None)=None) -> None:
    config = init(
        prog="kvmd",
        description="The main PiKVM daemon",
        argv=argv,
        check_run=True,
        load_auth=True,
        load_hid=True,
        load_atx=True,
        load_msd=True,
        load_gpio=True,
    )[2]

    msd_kwargs = config.kvmd.msd._unpack(ignore=["type"])
    if config.kvmd.msd.type == "otg":
        msd_kwargs["gadget"] = config.otg.gadget  # XXX: Small crutch to pass gadget name to the plugin

    hid_kwargs = config.kvmd.hid._unpack(ignore=["type", "keymap", "ignore_keys", "mouse_x_range", "mouse_y_range"])
