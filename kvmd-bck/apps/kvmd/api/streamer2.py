from aiohttp.web import Request
from aiohttp.web import Response

from ....htserver import UnavailableError
from ....htserver import exposed_http
from ....htserver import make_json_response

from ....validators import check_string_in_list
from ....validators.basic import valid_bool
from ....validators.basic import valid_number
from ....validators.basic import valid_int_f0
from ....validators.basic import valid_string_list
from ....validators.kvm import valid_stream_quality

from ..streamer2 import Streamer2

from ..ocr import Ocr


# =====
class StreamerApi2:
    def __init__(self, streamer: Streamer2, ocr: Ocr) -> None:
        self.__streamer = streamer
        self.__ocr = ocr

    # =====

    @exposed_http("GET", "/streamer2")
    async def __state_handler(self, _: Request) -> Response:
        return make_json_response(await self.__streamer.get_state())
