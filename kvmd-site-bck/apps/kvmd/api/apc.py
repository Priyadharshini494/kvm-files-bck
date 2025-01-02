import re
import os
import stat
import functools
import struct
import serial
import asyncio
import subprocess
from typing import Callable
from aiohttp import web
import paramiko
from functools import wraps

from aiohttp.web import Request
from aiohttp.web import Response
from ....htserver import exposed_http
from ....htserver import exposed_ws
from ....htserver import make_json_response
from ....htserver import WsSession
from ....logging import get_logger
from ....validators import raise_error

PDU_OUTLET_SUT = "1"  # Replace with your specific PDU outlet
PDU_TYPE = "apc"  # Replace with your PDU type (either 'raritan' or 'apc')
class ApcApi:
    def __init__(self) -> None:
        pass

    async def execute_gpio_command(self):
        try:
            get_logger(0).info("Executing GPIO command...")
            process = await asyncio.create_subprocess_exec(
                'raspi-gpio', 'set', '8', 'ip',
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                get_logger(0).error(f"Error executing GPIO command: {stderr.decode()}")
                return f"Error executing GPIO command: {stderr.decode()}"
            get_logger(0).info(f"GPIO command executed successfully: {stdout.decode()}")
            return "GPIO command executed successfully"
        except Exception as e:
            get_logger(0).error(f"Exception during GPIO command execution: {str(e)}")
            return f"Exception during GPIO command execution: {str(e)}"

    async def power_off(self, ip_address, username, password, pdu_outlet_sut=PDU_OUTLET_SUT, pdu_type=PDU_TYPE):
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(ip_address, username=username, password=password)
            get_logger(0).info("Connected successfully!")

            if pdu_type.lower() == "raritan":
                ssh_shell = ssh_client.invoke_shell()
                await asyncio.sleep(2)

                get_logger(0).info("Powering off...")
                ssh_shell.send(f"power outlets {pdu_outlet_sut} OFF\n")
                await asyncio.sleep(2)
                ssh_shell.send("y\n")
                await asyncio.sleep(180)  # Extended delay after power-off
            elif pdu_type.lower() == "apc":
                await asyncio.sleep(2)
                get_logger(0).info("Powering off...")
                stdin, stdout, stderr = ssh_client.exec_command(f'olOff {pdu_outlet_sut}')
                output = stdout.read().decode()
                get_logger(0).info(f"Command 'olOff {pdu_outlet_sut}' output:\n{output}")
                await asyncio.sleep(2)

            ssh_client.close()
            get_logger(0).info("SSH connection closed.")
            return "Power off successful.", 200
            # return make_json_response({
            #         'message': 'Power off successful.'
            #     },200)

        except paramiko.AuthenticationException:
            get_logger(0).error("Authentication failed. Please check your credentials.")
            return "Authentication failed. Please check your credentials.", 400
            # return make_json_response({
            #         'message': 'Authentication failed. Please check your credentials.'
            #     },400)
        except paramiko.SSHException as e:
            get_logger(0).error(f"SSH error: {str(e)}")
            return f"SSH error: {str(e)}", 500
            # return make_json_response({
            #         'SSH error': str(e)
            #     },500)
        except Exception as e:
            get_logger(0).error(f"An error occurred: {str(e)}")
            return f"An error occurred: {str(e)}", 500
            # return make_json_response({
            #         'Error': str(e)
            #     },500)

    async def power_on(self, ip_address, username, password, pdu_outlet_sut=PDU_OUTLET_SUT, pdu_type=PDU_TYPE):
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(ip_address, username=username, password=password)
            get_logger(0).info("Connected successfully!")

            if pdu_type.lower() == "raritan":
                ssh_shell = ssh_client.invoke_shell()
                await asyncio.sleep(2)

                get_logger(0).info("Powering on...")
                ssh_shell.send(f"power outlets {pdu_outlet_sut} ON\n")
                await asyncio.sleep(2)
                ssh_shell.send("y\n")
                await asyncio.sleep(180)  # Extended delay after power-on

            elif pdu_type.lower() == "apc":
                await asyncio.sleep(2)
                get_logger(0).info("Powering on...")
                stdin, stdout, stderr = ssh_client.exec_command(f'olOn {pdu_outlet_sut}')
                output = stdout.read().decode()
                get_logger(0).info(f"Command 'olOn {pdu_outlet_sut}' output:\n{output}")
                await asyncio.sleep(2)

            await asyncio.sleep(120)  # Additional delay
            ssh_client.close()
            get_logger(0).info("SSH connection closed.")
            return "Power on operation successful", 200

        except paramiko.AuthenticationException:
            get_logger(0).error("Authentication failed. Please check your credentials.")
            return "Authentication failed. Please check your credentials.", 400
        except paramiko.SSHException as e:
            get_logger(0).error(f"SSH error: {str(e)}")
            return f"SSH error: {str(e)}", 500
        except Exception as e:
            get_logger(0).error(f"An error occurred: {str(e)}")
            return f"An error occurred: {str(e)}", 500

    @exposed_http('POST', '/apc-power-off')
    # async def apc_power_off(request):
    async def apc_power_off(self, request: Request) -> Response:
        try:
            data = await request.json()
            ip_address = data.get('ip_address')
            username = data.get('username')
            password = data.get('password')

            if not all([ip_address, username, password]):
                return make_json_response({"error": "IP address, username, and password are required fields."}, status=400)

            message, status = await self.power_off(ip_address, username, password)
            return make_json_response({"message": message}, status=status)

        except Exception as e:
            get_logger(0).error(f"Request processing error: {str(e)}", exc_info=True)
            return make_json_response({"error": "An error occurred processing the request."}, status=500)

    @exposed_http('POST', '/apc-power-on')
    # async def apc_power_on(request):
    async def apc_power_on(self, request: Request) -> Response:
        try:
            data = await request.json()
            ip_address = data.get('ip_address')
            username = data.get('username')
            password = data.get('password')

            if not all([ip_address, username, password]):
                return make_json_response({"error": "IP address, username, and password are required fields."}, status=400)

            # Execute GPIO command before power on
            gpio_result = await self.execute_gpio_command()
            if "Error" in gpio_result:
                return make_json_response({"error": gpio_result}, status=500)

            message, status = await self.power_on(ip_address, username, password)
            return make_json_response({"message": message}, status=status)

        except Exception as e:
            get_logger(0).error(f"Request processing error: {str(e)}", exc_info=True)
            return make_json_response({"error": "An error occurred processing the request."}, status=500)
