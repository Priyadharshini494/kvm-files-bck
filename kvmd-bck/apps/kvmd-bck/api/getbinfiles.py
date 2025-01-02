import os
from aiohttp import web
from aiohttp.web import Request
from aiohttp.web import Response
from ....logging import get_logger
from ....htserver import exposed_http
from ....htserver import exposed_ws
from ....htserver import make_json_response
from ....htserver import WsSession
from ....logging import get_logger
from ....validators import raise_error

class GetbinfilesApi:
    def __init__(self) -> None:
        pass
    async def find_bin_files(self,start_directory='/binfile'):
        bin_files = []
        for dirpath, _, filenames in os.walk(start_directory):
            for filename in filenames:
                if filename.endswith('.bin'):
                    full_path = os.path.join(dirpath, filename)
                    bin_files.append(full_path)
        get_logger(0).info(f"Found bin files: {bin_files}")
        return bin_files

    @exposed_http('GET', '/bin-files')
    async def get_bin_files(self,request: Request) -> Response:
        try:
            bin_files = await self.find_bin_files()
            return make_json_response(bin_files,wrap_result=False)
            # return make_json_response({"ok": True, "result": bin_files})
            #return make_json_response(result=bin_files, wrap_result=False)
        except Exception as e:
            get_logger(0).error(f"Request processing error: {str(e)}", exc_info=True)
            return make_json_response({"error": "An error occurred processing the request."}, status=500)
