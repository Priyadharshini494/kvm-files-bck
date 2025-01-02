import subprocess
from aiohttp import web
from aiohttp.web import Request, Response
from ....logging import get_logger
from ....htserver import exposed_http, make_json_response
import json
from typing import Any
import re


class GetDriveApi:
    def __init__(self) -> None:
        self.previous_devices = set()


    async def fetch_disk(self):
        """Fetches disk usage information and identifies newly mounted devices."""
        try:
            # Run 'lsblk -o NAME,MAJ:MIN,RM,SIZE,RO,TYPE,MOUNTPOINT' command and capture the output
            result = subprocess.run(
                ['lsblk', '-o', 'NAME,MAJ:MIN,RM,SIZE,RO,TYPE,MOUNTPOINT'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                get_logger(0).error(
                    f"Command failed with return code {result.returncode}: {result.stderr.strip()}"
                )
                return {"error": result.stderr.strip()}

            # Log the output for debugging
            get_logger(0).debug(f"'lsblk' output:\n{result.stdout}")

            # Process the output to detect removable devices
            lines = result.stdout.strip().split('\n')
            removable_devices = []

            for line in lines[1:]:  # Skip header
                columns = line.split()
                if len(columns) >= 6 and columns[5] == 'disk' and columns[2] == '1':
                    # Check for removable (USB) devices by RM column (1 means removable)
                    # Exclude 'sda' and include any other 'sdX' devices
                    if columns[0] != 'sda' and columns[0].startswith('sd'):
                        removable_devices.append({
                            "device": columns[0],        # e.g., 'sdb', 'sdc', etc.
                            "size": columns[3],          # e.g., '460.3G'
                            "type": columns[5],          # e.g., 'disk'
                            "mounted_on": columns[6] if len(columns) > 6 else "Not Mounted"
                        })

            get_logger(0).info(f"Detected removable devices: {removable_devices}")
            return {"removable_devices": removable_devices}

        except FileNotFoundError:
            get_logger(0).error("lsblk command not found.")
            return {"error": "lsblk command not found. Ensure it is installed and available in PATH."}
        except PermissionError:
            get_logger(0).error("Insufficient permissions to execute lsblk command.")
            return {"error": "Insufficient permissions to execute lsblk command."}
        except Exception as e:
            get_logger(0).error(f"Unexpected error: {str(e)}", exc_info=True)
            return {"error": "Failed to fetch disk usage information."}

    @exposed_http('GET', '/removable-drives')
    async def get_removable_drives(self, request: Request) -> Response:
        """Handles HTTP GET requests to fetch removable drives."""
        try:
            removable_devices = await self.fetch_disk()
            return make_json_response(removable_devices, wrap_result=False)
        except Exception as e:
            get_logger(0).error(f"Request processing error: {str(e)}", exc_info=True)
            return make_json_response(
                {"error": "An error occurred processing the request."},
                status=500
            )

    async def fetch_disk_partitions(self, device: str) -> dict[str, Any]:
        """Fetches partitions for a specified device using lsblk."""
        try:
            # Run 'lsblk' to fetch detailed partition info in JSON format
            result = subprocess.run(
                ['lsblk', '-J', f'/dev/{device}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                get_logger(0).error(
                    f"Command failed with return code {result.returncode}: {result.stderr.strip()}"
                )
                return {"error": result.stderr.strip()}

            # Parse the JSON output from lsblk
            get_logger(0).info(f"'lsblk' output:\n{result.stdout}")
            data = json.loads(result.stdout)
            partitions = []
            for block in data.get("blockdevices", []):
            # Check if this device has child partitions
                if "children" in block:
                    for child in block["children"]:
                        mountpoints = child.get("mountpoints", [None])
                        mounted_on = mountpoints[0] if mountpoints[0] else "Not mounted"
                        partitions.append({
                            "device": f"/dev/{child['name']}",
                            "size": child.get("size", "N/A"),
                            "fstype": child.get("fstype", "N/A"),
                            "mounted_on": mounted_on
                        })
                else:
                    # For the parent device with no partitions or mount points
                    mountpoints = block.get("mountpoints", [None])
                    mounted_on = mountpoints[0] if mountpoints[0] else "Not mounted"
                    partitions.append({
                        "device": f"/dev/{block['name']}",
                        "size": block.get("size", "N/A"),
                        "fstype": block.get("fstype", "N/A"),
                        "mounted_on": mounted_on
                    })

            if not partitions:
                get_logger(0).info(f"No partitions found for device {device}")
                return {"error": f"No partitions found for device {device}"}

            # Log and return detected partitions
            get_logger(0).info(f"Detected partitions for {device}: {partitions}")
            return {"partitions": partitions}

            # for block in data.get("blockdevices", []):
            #     # Check if this device has child partitions
            #     if "children" in block:
            #         for child in block["children"]:
            #             if child.get("mountpoints") and child["mountpoints"][0]:
            #                 partitions.append({
            #                     "device": f"/dev/{child['name']}",
            #                     "size": child.get("size", "N/A"),
            #                     "fstype": child.get("fstype", "N/A"),
            #                     "mounted_on": child["mountpoints"][0]
            #                 })
            #     elif block.get("mountpoints") and block["mountpoints"][0]:  # For parent devices with a mount point
            #         partitions.append({
            #             "device": f"/dev/{block['name']}",
            #             "size": block.get("size", "N/A"),
            #             "fstype": block.get("fstype", "N/A"),
            #             "mounted_on": child["mountpoints"][0]
            #         })

            # if not partitions:
            #     get_logger(0).info(f"No mounted partitions found for device {device}")
            #     return {"error": f"No mounted partitions found for device {device}"}

            # # Log and return detected partitions
            # get_logger(0).info(f"Detected partitions for {device}: {partitions}")
            # return {"partitions": partitions}

        except FileNotFoundError:
            get_logger(0).error("lsblk command not found.")
            return {"error": "lsblk command not found. Ensure it is installed and available in PATH."}
        except PermissionError:
            get_logger(0).error("Insufficient permissions to execute lsblk command.")
            return {"error": "Insufficient permissions to execute lsblk command."}
        except json.JSONDecodeError:
            get_logger(0).error("Failed to parse lsblk output.")
            return {"error": "Failed to parse lsblk output. Ensure lsblk is functioning correctly."}
        except Exception as e:
            get_logger(0).error(f"Unexpected error: {str(e)}", exc_info=True)
            return {"error": "Failed to fetch partition information."}


    @exposed_http('POST', '/mount-drive')
    async def mount_drive(self, request: Request) -> Response:
        """Handles HTTP POST requests to mount a drive."""
        try:
            # Extract the drive name (e.g., sdb or sdc) from the request payload
            data = await request.json()
            drive = data.get('drive')
            if not drive:
                return make_json_response({"error": "Drive not specified"}, status=400)

            # Get partitions for the drive
            partitions = await self.fetch_disk_partitions(drive)
            get_logger(0).info(partitions)
            if 'error' in partitions:
                return make_json_response(partitions, status=400)

            partition_list = partitions.get("partitions", [])
            if not partition_list:
                return make_json_response({"error": f"No partitions found for drive {drive}"}, status=400)

            # Collect partitions that are mounted
            partition_names = []
            for partition in partition_list:
                if partition.get("mounted_on"):
                    partition_names.append(partition["device"].split('/')[-1])

            if not partition_names:
                return make_json_response({"error": f"No mounted partitions found for drive {drive}"}, status=400)

            # Unmount partitions
            unmount_result = await self.unmount_partitions(partition_names)
            if unmount_result.get("error"):
                return make_json_response(unmount_result, status=500)

            # Run the kvmd-otgmsd command
            kvmd_result = await self.run_kvmd_command(drive)
            if kvmd_result.get("error"):
                return make_json_response(kvmd_result, status=500)

            # Return success
            return make_json_response({"message": f"Drive {drive} mounted successfully"}, status=200)

        except Exception as e:
            get_logger(0).error(f"Unexpected error: {str(e)}", exc_info=True)
            return make_json_response({"error": "An error occurred while processing the request."}, status=500)

    async def unmount_partitions(self, partitions):
        """Unmount each partition of the drive."""
        get_logger(0).debug(f"Unmounting partitions: {partitions}")  # Log partitions to be unmounted
        for partition in partitions:
            try:
                # Run sudo umount to unmount the partition
                result = subprocess.run(
                    ['sudo','umount', f'/dev/{partition}'],  # Specify the full device path for unmount
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                if result.returncode != 0:
                # If the partition is already unmounted, continue without error
                    if "not mounted" in result.stderr:
                        get_logger(0).info(f"{partition} is already unmounted.")
                    else:
                        return {"error": f"Failed to unmount {partition}: {result.stderr.strip()}"}

                get_logger(0).info(f"Successfully unmounted {partition}")

                # if result.returncode != 0:
                #     return {"error": f"Failed to unmount {partition}: {result.stderr.strip()}"}

            except Exception as e:
                get_logger(0).error(f"Error unmounting {partition}: {str(e)}", exc_info=True)
                return {"error": f"Failed to unmount {partition}"}

        return {}

    async def run_kvmd_command(self, drive: str):
        """Run the kvmd-otgmsd command to configure the device."""
        try:
            # Run the kvmd-otgmsd command
            result = subprocess.run(
                ['sudo','kvmd-otgmsd', '--set-device', f'/dev/{drive}', '--set-cdrom', '0', '--set-rw', '1'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                return {"error": f"Failed to run kvmd-otgmsd for {drive}: {result.stderr.strip()}"}

            return {}

        except Exception as e:
            get_logger(0).error(f"Error running kvmd-otgmsd: {str(e)}", exc_info=True)
            return {"error": "Error running kvmd-otgmsd command."}

    @exposed_http('POST', '/unmount-drive')
    async def unmount_drive(self, request: Request) -> Response:
        try:
            data = await request.json()
            drive = data.get('drive')
            if not drive:
                return make_json_response({"error": "Drive not specified"}, status=400)
            kvmd_result = subprocess.run(
                ['sudo','kvmd-otgmsd', '--eject'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if kvmd_result.returncode != 0:
                return make_json_response({"error": "Error running kvmd-otgmsd --eject command."}, status=500)

            # return make_json_response({"message": "Drive unmounted successfully"}, status=200)
            get_logger(0).info("Drive unmounted successfully using kvmd-otgmsd.")
            usbip_output = subprocess.run(
            ['usbip', 'port'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
            )

            if usbip_output.returncode != 0:
                return make_json_response({"error": "Error fetching USB ports."}, status=500)

            # Extract the port number from the output
            match = re.search(r'Port (\d+):', usbip_output.stdout)
            if not match:
                return make_json_response({"error": "Port number not found in usbip output."}, status=500)

            port = match.group(1)

            # If port is 0, give it as 0; otherwise, change the port number
            if port == '0':
                return make_json_response({"port": 0}, status=200)

            # Run the detach command if the port is not 0
            detach_result = subprocess.run(
                ['sudo', 'usbip', 'detach', '--port', port],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if detach_result.returncode != 0:
                return make_json_response({"error": f"Error detaching port {port}"}, status=500)

            return make_json_response({"message": f"Drive unmounted from port {port} successfully"}, status=200)
        except Exception as e:
            get_logger(0).error(f"Error running kvmd-otgmsd --eject", exc_info=True)
            return make_json_response({"error": "Error running kvmd-otgmsd --eject command."}, status=500)

    @exposed_http('POST', '/get-drive-list')
    async def get_drive(self, request: Request) -> Response:
        try:
            data = await request.json()
            drive = data.get('ipaddress')
            if not drive:
                return make_json_response({"error": "IP Address specified"}, status=400)
            kvmd_result = subprocess.run(
                ['sudo','kvmd-otgmsd', '--eject'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if kvmd_result.returncode != 0:
                return make_json_response({"error": "Error running kvmd-otgmsd --eject command."}, status=500)

            # return make_json_response({"message": "Drive unmounted successfully"}, status=200)
            get_logger(0).info("Drive unmounted successfully using kvmd-otgmsd.")
            usbip_output = subprocess.run(
            ['usbip', 'port'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
            )

            if usbip_output.returncode != 0:
                return make_json_response({"error": "Error fetching USB ports."}, status=500)

            # Extract the port number from the output
            match = re.search(r'Port (\d+):', usbip_output.stdout)
            if not match:
                return make_json_response({"error": "Port number not found in usbip output."}, status=500)

            port = match.group(1)

            # If port is 0, give it as 0; otherwise, change the port number
            if port == '0':
                return make_json_response({"port": 0}, status=200)

            # Run the detach command if the port is not 0
            detach_result = subprocess.run(
                ['sudo', 'usbip', 'detach', '--port', port],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if detach_result.returncode != 0:
                return make_json_response({"error": f"Error detaching port {port}"}, status=500)

            return make_json_response({"message": f"Drive unmounted from port {port} successfully"}, status=200)
        except Exception as e:
            get_logger(0).error(f"Error running kvmd-otgmsd --eject", exc_info=True)
            return make_json_response({"error": "Error running kvmd-otgmsd --eject command."}, status=500)

    @exposed_http('POST', '/attach-usb')
    async def attachusb(self, request: Request) -> Response:
        try:
            data = await request.json()
            busid = data.get('busid')
            ipaddress = data.get('ipaddress')
            if not busid:
                return make_json_response({"error": "BUS-ID not specified"}, status=400)
            # Run the kvmd-otgmsd command
            result = subprocess.run(
                ['sudo','usbip','attach', f'--remote={ipaddress}', f'--busid={busid}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                return make_json_response({"error": f"Failed to attach {busid} of {ipaddress}: {result.stderr.strip()}"}, status=500)

    # Parse and return the command's output
            return make_json_response({"output": result.stdout.strip()}, status=200)

        except Exception as e:
            get_logger(0).error(f"Error attaching USB drive: {str(e)}", exc_info=True)
            return make_json_response({"error": "Error attaching USB drive."}, status=500)

    @exposed_http('POST', '/get-usb-list')
    async def usb_list(self, request: Request) -> Response:
        try:
            data = await request.json()
            ipaddress = data.get('ipaddress')
            if not ipaddress:
                return make_json_response({"error": "Ipaddress not specified"}, status=400)
            # Run the kvmd-otgmsd command
            result = subprocess.run(
                ['usbip','list', f'--remote={ipaddress}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                return make_json_response({"error": f"Failed to run usbip list for {ipaddress}: {result.stderr.strip()}"}, status=500)

    # Parse and return the command's output
            return make_json_response({"output": result.stdout.strip()}, status=200)

        except Exception as e:
            get_logger(0).error(f"Error running usbip list: {str(e)}", exc_info=True)
            return make_json_response({"error": "Error running usb list command."}, status=500)

    async def df_state(self):
        try:
            # Run 'df -h' command and capture the output
            result = subprocess.run(
                ['sudo', 'df', '-h'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                get_logger(0).error(
                    f"Command failed with return code {result.returncode}: {result.stderr.strip()}"
                )
                return {"error": result.stderr.strip()}

            # Log the output for debugging
            get_logger(0).info(f"'df -h' output:\n{result.stdout}")

            # Process the output to detect removable devices
            lines = result.stdout.strip().split('\n')
            removable_devices = []

            for line in lines[1:]:  # Skip header
                columns = line.split()
                if len(columns) >= 6 and columns[0].startswith('/dev/sd') and not columns[0].startswith('/dev/sda'):
                    # Add to the removable devices list
                    removable_devices.append({
                        "filesystem": columns[0],
                        "size": columns[1],
                        "used": columns[2],
                        "avail": columns[3],
                        "use%": columns[4],
                        "mounted_on": columns[5]
                    })

            get_logger(0).info(f"Detected removable devices: {removable_devices}")
            return {"removable_devices": removable_devices}

        except FileNotFoundError:
            get_logger(0).error("df command not found.")
            return {"error": "df command not found. Ensure it is installed and available in PATH."}
        except PermissionError:
            get_logger(0).error("Insufficient permissions to execute df command.")
            return {"error": "Insufficient permissions to execute df command."}
        except Exception as e:
            get_logger(0).error(f"Unexpected error: {str(e)}", exc_info=True)
            return {"error": "Failed to fetch disk usage information."}

    @exposed_http('GET', '/df-drives')
    async def get_df_drives(self, request: Request) -> Response:
        """Handles HTTP GET requests to fetch removable drives."""
        try:
            removable_devices = await self.df_state()
            return make_json_response(removable_devices, wrap_result=False)
        except Exception as e:
            get_logger(0).error(f"Request processing error: {str(e)}", exc_info=True)
            return make_json_response(
                {"error": "An error occurred processing the request."},
                status=500
            )
