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
    if config.kvmd.hid.type == "otg":
        hid_kwargs["udc"] = config.otg.udc  # XXX: Small crutch to pass UDC to the plugin

    global_config = config
    config = config.kvmd
    get_logger().info(str(config))
    hid = get_hid_class(config.hid.type)(**hid_kwargs)
    streamer = Streamer(
        **config.streamer._unpack(ignore=["forever", "desired_fps", "resolution", "h264_bitrate", "h264_gop"]),
        **config.streamer.resolution._unpack(),
        **config.streamer.desired_fps._unpack(),
        **config.streamer.h264_bitrate._unpack(),
        **config.streamer.h264_gop._unpack(),
    )
    #streamer2 = None
    streamer2 = Streamer2(
        **config.streamer2._unpack(ignore=["forever", "desired_fps", "resolution", "h264_bitrate", "h264_gop"]),
        **config.streamer2.resolution._unpack(),
        **config.streamer2.desired_fps._unpack(),
        **config.streamer2.h264_bitrate._unpack(),
        **config.streamer2.h264_gop._unpack(),
    )

    streamer3 = Streamer3(
        **config.streamer3._unpack(ignore=["forever", "desired_fps", "resolution", "h264_bitrate", "h264_gop"]),
        **config.streamer3.resolution._unpack(),
        **config.streamer3.desired_fps._unpack(),
        **config.streamer3.h264_bitrate._unpack(),
        **config.streamer3.h264_gop._unpack(),
    )

    streamer4 = Streamer4(
        **config.streamer4._unpack(ignore=["forever", "desired_fps", "resolution", "h264_bitrate", "h264_gop"]),
        **config.streamer4.resolution._unpack(),
        **config.streamer4.desired_fps._unpack(),
        **config.streamer4.h264_bitrate._unpack(),
        **config.streamer4.h264_gop._unpack(),
    )
	# Modified code block for MSD initialization
    try:
        msd = get_msd_class(config.msd.type)(**msd_kwargs)
    except RuntimeError as e:
        if "Can't find 'otgmsd' mountpoint" in str(e):
            # Log the error or handle it as per your requirement
            get_logger(0).warning("MSD mountpoint 'otgmsd' not found. MSD functionality will be disabled.")
            msd = None
        else:
            # Log other RuntimeError exceptions
            get_logger(0).error(f"Error initializing MSD: {e}")
            msd = None
    except Exception as e:
        # Log other exceptions
        get_logger(0).error(f"Error initializing MSD: {e}")
        msd = None
    KvmdServer(
        auth_manager=AuthManager(
            enabled=config.auth.enabled,
            unauth_paths=([] if config.prometheus.auth.enabled else ["/export/prometheus/metrics"]),

            internal_type=config.auth.internal.type,
            internal_kwargs=config.auth.internal._unpack(ignore=["type", "force_users"]),
            force_internal_users=config.auth.internal.force_users,

            external_type=config.auth.external.type,
            external_kwargs=(config.auth.external._unpack(ignore=["type"]) if config.auth.external.type else {}),

            totp_secret_path=config.auth.totp.secret.file,
        ),
        info_manager=InfoManager(global_config),
        #info_manager2=InfoManager2(global_config),
        info_manager2=None,
        info_manager3=None,
        info_manager4=None,
        log_reader=(LogReader() if config.log_reader.enabled else None),
        user_gpio=UserGpio(config.gpio, global_config.otg),
        ocr=Ocr(**config.ocr._unpack()),

        hid=hid,
        atx=get_atx_class(config.atx.type)(**config.atx._unpack(ignore=["type"])),
        msd=msd,
        streamer=streamer,
        streamer2 = streamer2,
        streamer3 = streamer3,
        streamer4 = streamer4,
        snapshoter=Snapshoter(
            hid=hid,
            streamer=streamer,
            **config.snapshot._unpack(),
        ),
        
        keymap_path=config.hid.keymap,
        ignore_keys=config.hid.ignore_keys,
        mouse_x_range=(config.hid.mouse_x_range.min, config.hid.mouse_x_range.max),
        mouse_y_range=(config.hid.mouse_y_range.min, config.hid.mouse_y_range.max),

        stream_forever=config.streamer.forever,
        stream_forever2=config.streamer2.forever,
        stream_forever3=config.streamer3.forever,
        stream_forever4=config.streamer4.forever,
    ).run(**config.server._unpack())

    get_logger(0).info("Bye-bye")
