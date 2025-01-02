import asyncio
import re
import socket
import threading
import serial
from aiohttp import web
from functools import wraps
from aiohttp.web import Request, Response
from ....htserver import exposed_http, make_json_response

# Initialize the serial port
port = serial.Serial("/dev/ttyGS0", baudrate=115200, timeout=2, xonxoff=False)

# Regex to remove ANSI escape sequences
regex = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# Static nav value
nav = '1'
cond_var = 0

# UDP Handler class (moved outside)
class UdpHandler:
    def __init__(self):
        self.message = ""
        self.port = None
        self.address = None
        self.lock = threading.Lock()
        self.start_udp_server() 

    def start_udp_server(self):
        threading.Thread(target=self.udp_server, daemon=True).start()

    def set_port(self, port):
        self.port = port

    def set_address(self, address):
        self.address = address

    def set_message(self, message):
        with self.lock:
            self.message += message + '\n'

    def get_message(self):
        with self.lock:
            return self.message

    def clear_message(self):
        with self.lock:
            self.message = ""

    def get_port(self):
        return self.port

    def get_address(self):
        return self.address

    # UDP server method
    def udp_server(self):
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.bind(('190.20.20.2', 4444))  # Bind to the specified IP and port

        while True:
            data, addr = udp_sock.recvfrom(1024)
            message = data.decode('utf-8').strip()
            print(f"Received message: {message} from {addr}")

            if message == "SYNC":
                self.set_port(addr[1])
                self.set_address(addr[0])
                udp_sock.sendto(b"SYNC", addr)
            else:
                self.set_message(message)


# Main UsbethernetApi class
class UsbethernetApi:
    def __init__(self,udphandler_api=None) -> None:
        self.udp_handler = UdpHandler()
        if udphandler_api is not None:
            self.udp_handler = udphandler_api

    async def taskRead(self):
        global cond_var
        cond_var = 1
        data = port.readline()
        while len(nav) != 0 and len(data) != 0:
            data = regex.sub('', data.decode('ascii'))
            if data == nav:
                port.readall()
                break
            data = port.readline()
        while len(nav) == 0 and len(data) != 0:
            print(regex.sub('', data.decode('ascii')))
            data = port.readline()
        cond_var = 0

    async def taskWrite(self, cmd):
        global cond_var
        port.flush()
        if len(nav) == 0:
            for byteChr in cmd:
                port.write(str.encode(byteChr, 'ascii'))
                await asyncio.sleep(0.25)
            await asyncio.sleep(1)
            port.write(str.encode('\r\n', 'ascii'))
            await asyncio.sleep(1)
        else:
            port.write(str.encode(cmd, 'utf-8'))
        while cond_var != 0:
            await asyncio.sleep(0.1)

    @exposed_http('GET', '/send_command')
    async def send_command(self, request: Request) -> Response:
        global cond_var
        cmd = request.query.get('cmd')
        
        if not cmd:
            return make_json_response({"error": "No command provided"}, status=400)
        
        read_thread = threading.Thread(target=asyncio.run, args=(self.taskRead(),))
        write_thread = threading.Thread(target=asyncio.run, args=(self.taskWrite(cmd),))
        
        read_thread.start()
        write_thread.start()
        
        read_thread.join()
        write_thread.join()
        
        return make_json_response({"status": "Command processed successfully"})

    @exposed_http('GET', '/ethernet')
    async def ethernet_usb(self, request: Request) -> Response:
        reqcmd = request.query.get('reqcmd')

        if reqcmd and reqcmd != "SYNC":
            port = self.udp_handler.get_port()
            address = self.udp_handler.get_address()

            if port and address:
                udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_sock.sendto(reqcmd.encode('utf-8'), (address, port))
                
                self.udp_handler.clear_message()  # Clear previous messages

                # Wait for responses
                await asyncio.sleep(1)  # 1 second delay to accumulate responses

                response = self.udp_handler.get_message()
                return make_json_response({"stdout": response}, status=200)
            else:
                return make_json_response({"error": "Invalid port or address"}, status=400)
        else:
            return make_json_response({"error": "No command provided or SYNC message ignored"}, status=400)


# The main entry point to register HTTP routes and run the web server can remain the same
