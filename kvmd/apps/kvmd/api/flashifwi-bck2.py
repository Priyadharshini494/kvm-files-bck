import aiohttp
import asyncio
import os
from aiohttp import web
from datetime import datetime
import subprocess
from functools import wraps
import aiofiles
from aiohttp.web import Request
from aiohttp.web import Response
from ....htserver import exposed_http
from ....htserver import exposed_ws
from ....htserver import make_json_response
from ....htserver import WsSession
from ....logging import get_logger
from ....validators import raise_error
import shutil
class FlashifwiApi:
    def __init__(self) -> None:
        pass
    # Asynchronous function to run shell commands
    async def run_command(self,command):
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            output, error = await process.communicate()
            return process.returncode, output.decode('utf-8'), error.decode('utf-8')
        except Exception as e:
            return 1, "", str(e)
        
    # Asynchronous function to save output to a file
    async def save_output_to_file(self, file_path, content):
        async with aiofiles.open(file_path, 'a') as f:
            await f.write(content + '\n')

    # Asynchronous function to identify the flash chip
    async def identify_flash_chip(self, programmer):
        command = f"flashrom -p {programmer}"
        return await self.run_command(command)

    # Asynchronous function to flash firmware (commented section added)
    async def flash_firmware(self, programmer, firmware_file):
        command = f"flashrom -p {programmer} -w {firmware_file} --force -V"
        ret_code, output, error = await self.run_command(command)
        log_message = f"Flash Firmware Command: {command}\nOutput: {output}\nError: {error}\nReturn Code: {ret_code}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_log = f"/home/kvmd-webterm/output_log_{timestamp}.txt"
        await self.save_output_to_file(output_log, log_message)
        return await self.run_command(command)

    # Asynchronous function to verify flashing (commented section added)
    async def verify_flashing(self, programmer, firmware_file):
        command = f"flashrom -p {programmer} -r readback.bin && diff {firmware_file} readback.bin"
        return await self.run_command(command)

    # Asynchronous function to reset SPI
    async def reset_spi(self):
        await self.run_command("sudo systemctl restart spi")
        await asyncio.sleep(2)  # Increase delay to ensure SPI is reset

    async def has_enough_space(self, path, required_space_mb):
        total, used, free= shutil.disk_usage(path)
        return free // (1024 * 1024) >= required_space_mb

    # Exposed endpoint for flashing IFWI
    @exposed_http('GET', '/flash_ifwi')
    async def flash_ifwi(self, request):
        try:
            # Extract the IFWI file path from the GET request query parameters
            firmware_file = request.query.get('ifwi_file')

            # Programmer setup
            programmer = "linux_spi:dev=/dev/spidev0.0,spispeed=5000"

            # Create a timestamped log file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_log = f"/home/kvmd-webterm/output_log_{timestamp}.txt"

            # Check if the firmware file exists
            if not os.path.exists(firmware_file):
                error_message = f"Firmware file {firmware_file} does not exist."
                await self.save_output_to_file(output_log, error_message)
                return make_json_response({"error": error_message}, status=400)

            # Set GPIO 8 to output mode
            ret_code, output, error = await self.run_command("raspi-gpio set 8 op")
            await self.save_output_to_file(output_log, f"Set GPIO 8 to output mode.\nOutput: {output}\nError: {error}")

            # Identify Flash Chip (log output but don't block execution)
            await self.reset_spi()  # Reset SPI interface before identifying the flash chip
            ret_code, output, error = await self.identify_flash_chip(programmer)
            await self.save_output_to_file(output_log, f"Chip Identification:\nOutput: {output}\nError: {error}")
            if ret_code != 0:
                await self.save_output_to_file(output_log, "Chip identification failed. Proceeding to flash firmware.")

            # Flash IFWI Firmware
            flash_successful = False
            while not flash_successful:
                await self.reset_spi()  # Reset SPI interface before flashing the firmware
                await asyncio.sleep(5)  # Additional delay to ensure SPI is ready
                ret_code, output, error = await self.flash_firmware(programmer, firmware_file)
                await self.save_output_to_file(output_log, f"Flashing Firmware:\nOutput: {output}\nError: {error}")
                if "Erase/write done" in output:
                    flash_successful = True
                elif ret_code != 0:
                    await self.save_output_to_file(output_log, f"Flashing failed. Retrying...\nError: {error}")

            # Verify Flashing
            await self.reset_spi()  # Reset SPI interface before verifying the flashing
            await asyncio.sleep(5)  # Additional delay to ensure SPI is ready
            ret_code, output, error = await self.verify_flashing(programmer, firmware_file)
            await self.save_output_to_file(output_log, f"Verification:\nOutput: {output}\nError: {error}")
            if ret_code != 0:
                error_message = f"Error verifying flashing: {error}"
                await self.save_output_to_file(output_log, error_message)
                return web.json_response({"error": error_message}, status=500)

            # Set GPIO 8 to input mode
            ret_code, output, error = await self.run_command("raspi-gpio set 8 ip")
            await self.save_output_to_file(output_log, f"Set GPIO 8 to input mode.\nOutput: {output}\nError: {error}")

            return make_json_response({"message": "Firmware flashing successful"}, status=200)

        except Exception as e:
            return make_json_response({"error": str(e)}, status=500)