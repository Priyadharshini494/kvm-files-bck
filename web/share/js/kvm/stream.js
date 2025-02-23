/*****************************************************************************
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
*****************************************************************************/
"use strict";
import { tools, $ } from "../tools.js";
import { wm } from "../wm.js";
import { Camera } from "./camera.js";
import { JanusStreamer } from "./stream_janus.js";
import { MjpegStreamer } from "./stream_mjpeg.js";
import { MjpegStreamer2 } from "./stream_mjpeg.js";
import { MjpegStreamer3 } from "./stream_mjpeg.js";
import { MjpegStreamer4 } from "./stream_mjpeg.js";
export function Streamer() {
	var self = this;
	/************************************************************************/
	var __janus_enabled = null;
	var __streamer = null;
	var __state = null;
	var __resolution = { "width": 640, "height": 480 };
	var __init__ = function () {
		__streamer = new MjpegStreamer(__setActive, __setInactive, __setInfo);
		__applyBatteryStatus("Unavailable");
		tools.radio.setOnClick("Battery-options", __clickSimulationButton, false);
		tools.el.setOnClick($("battery-link"), __applyBatteryStatus);
		tools.el.setOnClick($("attachRealBattery"), __attachRealBattery);
		tools.el.setOnClick($("detachBattery"), __detachBattery);
		tools.el.setOnClick($("attachSimulatedBattery"), __attachSimulatedBattery);
		tools.el.setOnClick($("detachRealBattery"), __detachBattery);
                tools.el.setOnClick($("apc-power-off"), __apcpoweroff);
                tools.el.setOnClick($("apc-power-on"), __apcpoweron);
                tools.el.setOnClick($("apc-power-off2"), __apcpoweroff2);
                tools.el.setOnClick($("apc-power-on2"), __apcpoweron2);
                tools.el.setOnClick($("apc-power-off4"), __apcpoweroff4);
                tools.el.setOnClick($("apc-power-on4"), __apcpoweron4);
                tools.el.setOnClick($("get-boot-order"), __getbootorder);
                tools.el.setOnClick($("get-boot-order2"), __getbootorder);
                tools.el.setOnClick($("get-boot-order4"), __getbootorder);
                tools.el.setOnClick($("change-bootorder"), __changebootorder);
                tools.el.setOnClick($("change-bootorder2"), __changebootorder2);
                tools.el.setOnClick($("change-bootorder4"), __changebootorder4);
                tools.el.setOnClick($("edk-reset"), __resetedk);
                tools.el.setOnClick($("edk-reset2"), __resetedk);
                tools.el.setOnClick($("edk-reset4"), __resetedk);
                tools.el.setOnClick($("ifwi-flash"), __flashifwi);
                tools.el.setOnClick($("ifwi-flash2"), __flashifwi2);
                tools.el.setOnClick($("ifwi-flash4"), __flashifwi4);
                tools.el.setOnClick($("file-selection"), __getbinfiles);
      		tools.el.setOnClick($("file-selection2"), __getbinfiles2);
                tools.el.setOnClick($("file-selection4"), __getbinfiles4);
                tools.el.setOnClick($("switchSerialButton"),__switchSerialButton);
                tools.el.setOnClick($("switchEthernetButton"),__switchEthernetButton);
                tools.el.setOnClick($("switchSerialButton2"),__switchSerialButton);
                tools.el.setOnClick($("switchEthernetButton2"),__switchEthernetButton);
                tools.el.setOnClick($("switchSerialButton4"),__switchSerialButton);
                tools.el.setOnClick($("switchEthernetButton4"),__switchEthernetButton);
                tools.el.setOnClick($("send-button"), __sendcommand);
                tools.el.setOnClick($("send-button2"), __sendcommand2);
                tools.el.setOnClick($("send-button4"), __sendcommand4);
                tools.el.setOnClick($("postcode"), __show_postcode);
                tools.el.setOnClick($("msdu-image-selector"), __showusbdrive);
                tools.el.setOnClick($("msdu-mount-button"), __mountdrive);
                tools.el.setOnClick($("msdu-unmount-button"), __unmountdrive);
                tools.el.setOnClick($("usb-drive-selector"), __getusblist);
                tools.el.setOnClick($("attach-usb"), __attachusb);
		tools.el.setOnClick($("mount-info"), __clickUsbInfoButton);

                $("stream-led").title = "Stream inactive";
		tools.slider.setParams($("stream-quality-slider"), 5, 100, 5, 80, function (value) {
			$("stream-quality-value").innerHTML = `${value}%`;
		});
		tools.slider.setOnUpDelayed($("stream-quality-slider"), 1000, (value) => __sendParam("quality", value));
		tools.slider.setParams($("stream-h264-bitrate-slider"), 25, 20000, 25, 5000, function (value) {
			$("stream-h264-bitrate-value").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-bitrate-slider"), 1000, (value) => __sendParam("h264_bitrate", value));
		tools.slider.setParams($("stream-h264-gop-slider"), 0, 60, 1, 30, function (value) {
			$("stream-h264-gop-value").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-gop-slider"), 1000, (value) => __sendParam("h264_gop", value));
		tools.slider.setParams($("stream-desired-fps-slider"), 0, 120, 1, 0, function (value) {
			$("stream-desired-fps-value").innerHTML = (value === 0 ? "Unlimited" : value);
		});
		tools.slider.setOnUpDelayed($("stream-desired-fps-slider"), 1000, (value) => __sendParam("desired_fps", value));
		$("stream-resolution-selector").onchange = (() => __sendParam("resolution", $("stream-resolution-selector").value));
		tools.radio.setOnClick("stream-mode-radio", __clickModeRadio, false);
		tools.slider.setParams($("stream-audio-volume-slider"), 0, 100, 1, 0, function (value) {
			$("stream-video").muted = !value;
			$("stream-video").volume = value / 100;
			$("stream-audio-volume-value").innerHTML = value + "%";
			if (__streamer.getMode() === "janus") {
				let allow_audio = !$("stream-video").muted;
				if (__streamer.isAudioAllowed() !== allow_audio) {
					__resetStream();
				}
			}
		});
		tools.el.setOnClick($("stream-screenshot-button"), __clickScreenshotButton);
		tools.el.setOnClick($("stream-reset-button"), __clickResetButton);
	//	tools.el.setOnClick($("refresh-button-id"), __set_system_state);
                setInterval(__set_system_state, 2500);
                setInterval(__set_interface_state, 2500);
                //setInterval(__setPostcode, 2500);
                //setInterval(__updateText, 2500);
		$("stream-window").show_hook = () => __applyState(__state);
		$("stream-window").close_hook = () => __applyState(null);
                self.runInBackground();
                self.updateText();
                //self.startUpdateTextInterval();
        };
	/************************************************************************/
        self.runInBackground = async function() {
                while (true) {
                        await new Promise(resolve => setTimeout(resolve, 1000));
                        await __updateButtonState();
                        __setPostcode();
                }
        };
        setInterval(function () {
    let selectElement = document.getElementById("usb-drive-selector");
    selectElement.value = ""; // Reset to the default "Select a USB drive" option
}, 15000);
        var __updateButtonState = async function () {
    let removableDevices = [];

    function handleResponse() {
        if (http.readyState === 4 && http.status === 200) {
            const data = JSON.parse(http.responseText);
            if (data && data.removable_devices) {
                removableDevices = data.removable_devices;

                // Enable or disable buttons based on removable devices
                let mountButton = document.getElementById('msdu-mount-button');
                //     let unmountButton = document.getElementById('msdu-unmount-button');

                if (removableDevices.length > 0) {
                    // Enable buttons
                    mountButton.disabled = false;
                    //       unmountButton.disabled = false;
                } else {
                    // Disable buttons
                    mountButton.disabled = true;
                    //     unmountButton.disabled = true;
                }
            }
        } else if (http.readyState === 4 && http.status !== 200) {
            console.error("Failed to fetch removable drives:", http.statusText);

            // Disable buttons in case of error
            document.getElementById('msdu-mount-button').disabled = true;
            //document.getElementById('msdu-unmount-button').disabled = true;
        }
    }

    let http = tools.makeRequest("GET", "/api/df-drives", handleResponse);
};

var __attachusb = function () {
    let selectElement = document.getElementById("usb-drive-selector");
    let selectedValue = selectElement.value;  // Get the selected value (ipaddress:busid)

    // Check if a drive is selected
    if (!selectedValue) {
        wm.error("Please select a USB drive.");
        return;
    }
    // Clean the selected value by removing any unwanted characters (like " - " in front of the IP address)
    let cleanedSelectedValue = selectedValue.trim().replace(/^\s*-\s*/, "");  // Remove leading " - " and surrounding spaces

    // Log the cleaned selected value
    console.log("Cleaned Selected Value:", cleanedSelectedValue);

    // Now, split the cleaned value into ipaddress and busid
    let [ipaddress, busid] = cleanedSelectedValue.split(':');

    // Log the cleaned and extracted values for debugging
    console.log("Cleaned IP:", ipaddress, "Bus ID:", busid);

    // Validate IP address input
    if (!ipaddress || !/^(\d{1,3}\.){3}\d{1,3}$/.test(ipaddress)) {
        wm.error("Please enter a valid IP address.");
        return;
    }

    // Prepare the data for the API request
    let data = JSON.stringify({
        "ipaddress": ipaddress,
        "busid": busid,
    });
    let http = tools.makeRequest("POST", "/api/attach-usb", function () {
        if (http.readyState === 4) {
            if (http.status === 200) {
                let response = JSON.parse(http.responseText);
                if (response.ok) {
                    // Handle success (e.g., show a success message or update UI)
                    wm.info("USB drive attached successfully.");
                } else {
                    // Handle failure (e.g., show an error message)
                    wm.error("Failed to attach the USB drive.");
                }
            } else {
                wm.error("Error: " + http.statusText);
            }
        }
    }, data, "application/json");
};



let isUsbDropdownUpdated = false;
var __getusblist = function () {
    let ipaddress = document.getElementById("usb-ip").value;

    // Validate IP address input
    if (!ipaddress || !/^(\d{1,3}\.){3}\d{1,3}$/.test(ipaddress)) {
        alert("Please enter a valid IP address.");
        return;
    }

    let data = JSON.stringify({
        "ipaddress": ipaddress,
    });
    let http = tools.makeRequest("POST", "/api/get-usb-list", function () {
        if (http.readyState === 4) {
            if (http.status === 200) {
                try {
                    let responseData = JSON.parse(http.responseText);

                    if (responseData.ok && responseData.result && responseData.result.output) {
                        // Split and format response
                        let responseLines = responseData.result.output.split('\n').filter(line => line.trim() !== '');

                        // Initialize an empty array to hold USB drives
                        let usbDrives = [];
                        let ip = "";

                        // Process each line to extract busid, ipaddress, and drive info
                        responseLines.forEach(function (line) {
                            // Match IP address (on the line that starts with '-')
                            if (line.startsWith(" - ")) {
                                ip = line.replace(" - ", "").trim();
                                //ip = line.trim(); // Extract the IP Address
                            }

                            // Match the busid and USB description
                            let match = line.match(/^\s*(\d+-\d+):\s+([^\n]+)/);
                            if (match) {
                                let busid = match[1]; // BusID
                                let drive = match[2]; // USB Drive Description

                                // Add the formatted drive to the array if IP address is found
                                if (ip) {
                                    usbDrives.push({
                                        ipaddress: ip,
                                        busid: busid,
                                        drive: drive
                                    });
                                    ip = ""; // Reset IP after it is used
                                }
                            }
                        });
                        if (usbDrives.length > 0) {
                            let selectElement = document.getElementById("usb-drive-selector");
                            const selectedValue = selectElement.value;

                            // Clear dropdown options, but keep the placeholder
                            selectElement.innerHTML = "<option value=''>Select a USB drive</option>";
                            usbDrives.forEach(function (device) {
                                let option = document.createElement("option");
                                option.value = `${device.ipaddress}:${device.busid}`; // Set value as "ipaddress:busid"
                                option.text = `${device.busid} ${device.drive}`; // Set the text to show the full info
                                selectElement.appendChild(option);
                            });
                            if (selectedValue) {
                                selectElement.value = selectedValue;
                            }
                            isUsbDropdownUpdated = true;
                        } else {
                            wm.error("No USB drives found or invalid response.");
                        }
                    } else {
                        wm.error("No USB drives found or invalid response.");
                    }
                } catch (e) {
                    wm.error("Can't parse the response: " + e.message);
                }
            } else {
                try {
                    let errorResponse = JSON.parse(http.responseText);
                    wm.error("Can't get USB list: " + (errorResponse.error || "Unknown error"));
                } catch (e) {
                    wm.error("Error parsing error response: " + e.message);
                }
            }
        }
    }, data, "application/json");
};
document.getElementById("usb-drive-selector").addEventListener('change', function () {
    const selectedValue = this.text; // Get the selected value (ipaddress:busid)
    if (selectedValue) {
        console.log("You selected: " + selectedValue); // You can send this selected value or handle it as needed
    }
});

let driveloaded = false;

var __showusbdrive = function () {
    // Trigger the API call only when the user clicks the dropdown (or it is triggered)
    let http = tools.makeRequest("GET", "/api/removable-drives", function () {
        if (http.readyState === 4) {
            if (http.status === 200) {
                let response = JSON.parse(http.responseText);
                let selectElement = document.getElementById("msdu-image-selector");

                // Get the currently selected drive, if any, to preserve the selection after update
                const selectedDrive = selectElement.value;

                // Clear all options except for the placeholder
                selectElement.innerHTML = "<option value=''>Select a drive</option>";

                // Check if there are removable devices
                if (response.removable_devices && response.removable_devices.length > 0) {
                    response.removable_devices.forEach(function (device) {
                        //let filesystemLabel = device.filesystem.replace("/dev/", "");
                        // Create an option element for each drive
                        let option = document.createElement("option");
                        option.value = device.device;
                        option.text = `${device.device} (${device.size} available)`;
                        selectElement.appendChild(option);
                    });
                } else {
                    // If no drives are found, show a placeholder
                    let option = document.createElement("option");
                    option.value = "";
                    option.text = "No drives found";
                    selectElement.appendChild(option);
                }

                // After updating options, set the previously selected drive (if any) back as the selected value
                if (selectedDrive) {
                    selectElement.value = selectedDrive;
                }

                // Mark drives as loaded only if it's the first load
                if (!driveloaded) {
                    driveloaded = true;
                }
            } else {
                console.error("Failed to fetch removable drives:", http.statusText);
                wm.error("Error fetching removable drives.");
            }
        }
    });
};

document.getElementById('msdu-image-selector').addEventListener('change', function () {
    const selectedDrive = this.value;
    if (selectedDrive) {
        console.log(`Selected drive: ${selectedDrive}`);
    }
});

var __mountdrive = function () {
    wm.confirm("Are you sure you want to Mount Drive").then(function (ok) {
        if (ok) {
            // Gather the input value from the HTML
            let selected_drive = document.getElementById("msdu-image-selector").value;

            // Prepare the payload as a JSON object
            let payload = JSON.stringify({ drive: selected_drive });

            // Use the updated makeRequest function with the JSON payload
            tools.makeRequest("POST", "/api/mount-drive", function () {
                if (this.readyState === 4) {
                    if (this.status !== 200) {
                        wm.error("Click error:<br>", this.responseText);
                    }
                    if (this.status == 200) {
                        wm.info("Drive Mounted Successfully");
                    }
                }
            }, payload, "application/json"); // Set content type to JSON
        }
    });
};

var __clickUsbInfoButton = function() {
    wm.info("<div class='selectable-text'><b>Windows Users:</b><br><br>"+
	    "1. Open Windows PowerShell with administrator permissions on your local PC, and connect the pendrive to the USB port to PC.<br>" +
            "2. Provide the below commands:<br><br>" +
            "   <t><i>winget install usbipd</i></t><br>" +
            "   <i>usbipd list</i><br><br>" +
            "   The devices which are connected to the local PC will be listed along with BUSID, VID:PID, STATE.<br>" +
            "   Execute the below command:<br>" +
            "   <i>usbipd bind --busid=&lt;BUSID&gt</i> (replace &lt;BUSID&gt with the original BUSID of the device which you want to share)<br><br>" +
            "<b>Linux users:</b><br><br>" +
            "1. Open the command prompt on your local PC, and connect the pendrive to the USB port of your local PC.<br>" +
            "2. Provide the below commands:<br><br>" +
            "   <i>sudo apt install linux-tools-6.5.0-35-generic</i><br><br>" +
	    "	<i>sudo modprobe usbip_host</i><br>"+
	    "	<i>sudo nano /etc/modules (add the below lines)</i><br>"+
	    " 	<i>i2c-dev</i><br>"+
	    "	<i>usbip_host</i><br>"+
	    "	<i>usbip list -p -l</i><br><br>"+
            "   The devices which are connected to the local PC will be listed along with BUSID, VID:PID, STATE.<br>" +
            "   Execute the below command:<br><br>" +
            "   <i>sudo usbip bind --busid=&lt;BUSID&gt</i> (replace &lt;BUSID&gt with the original BUSID of the device which you want to share)<br>" +
            "   Finally, execute the below to start the daemon:<br><br>" +
            "   <i>sudo usbipd</i><br></div>"
    )
};

var __unmountdrive = function () {
    wm.confirm("Are you sure you want to Unmount Drive").then(function (ok) {
        if (ok) {
            let selected_drive = document.getElementById("msdu-image-selector").value;
            let payload = JSON.stringify({ drive: selected_drive });
            // Use the updated makeRequest function to send a GET request
            tools.makeRequest("POST", "/api/unmount-drive", function () {
                if (this.readyState === 4) {
                    if (this.status !== 200) {
                        wm.error("Unmount error:<br>", this.responseText);
                    } if (this.status == 200) {
                        wm.info("Drive unmounted successfully.");
                    }
                }
            }, payload, "application/json");
        }
    });
};

        self.updateText = function() {
                console.log("Update Text called");
                let dataArray = JSON.parse(sessionStorage.getItem('hexdata')) || [];
                const el_grab2 = document.querySelector("#stream-window-header .window-postcode");
                let el_info = $("stream-info");
                if (dataArray.length > 0) {
                        sessionStorage.setItem('last_item', dataArray[0])
                        const newText = 'Postcode: ' + sessionStorage.getItem('last_item');
                        el_grab2.innerHTML = el_info.innerHTML = newText;
                        dataArray.shift();
                        console.log(dataArray);
                        sessionStorage.setItem('hexdata', JSON.stringify(dataArray));
                        setTimeout(() => {self.updateText();}, 100);
                } else {
                        console.log("Hex Data deleted");
                        const lastItem = sessionStorage.getItem('last_item');
        if (lastItem) {
            const newText = 'Postcode: ' + lastItem;
            el_grab2.innerHTML = el_info.innerHTML = newText; // Display the last item
        } else {
            console.log("No last item found in session storage.");
            el_grab2.innerHTML = el_info.innerHTML = 'No postcode available'; // Fallback message
        }
                        sessionStorage.removeItem('hexdata');
                        sessionStorage.setItem('updating', '0');
                }
        };
       
        var __show_postcode = function(){
                   let http = tools.makeRequest("GET", "/api/postcode/get_logs", function() {
                           if (http.readyState === 4) {
                                   if (http.status === 200) {
                                            let response = JSON.parse(http.responseText);
                                            let logs = response.result.Logs;
                                            let logsString = logs.join("<br>");
                                           wm.info("Postcode Logs:<br>" + logsString);
                                   }
                               }
                            });

                        };
        var __setPostcode = function() {
                console.log("Calling __setPostcode function");
                let postcodeValues = [];
                function handleResponse() {
                    if (http.readyState === 4 && http.status === 200) {
                        const data = JSON.parse(http.responseText);
                        if (data && data.result && data.result.hexdata) {
                            sessionStorage.setItem("lastline",data.result.Linenumber);
                            postcodeValues = data.result.hexdata;
                            let dataArray = JSON.parse(sessionStorage.getItem('hexdata')) || [];
                            let full_data = dataArray.concat(postcodeValues);
                            if (full_data.length > 0) {
                                    sessionStorage.setItem('hexdata', JSON.stringify(dataArray.concat(postcodeValues)));
                                    if (sessionStorage.getItem('updating') || '0' === '0') {
                                            self.updateText();
                                            sessionStorage.setItem('updating', '1');
                                    }
                            }
                        }
                    }
                }
                let http = tools.makeRequest("GET", "/api/postcode/get_data?lastline=" + sessionStorage.getItem('lastline'), handleResponse);
        };
        
	var __detachBattery = function () {
		let http = tools.makeRequest("POST", `/api/battery/ac-source`, function () {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					wm.error("Click error:<br>", http.responseText);
				}
				else {
					__applyBatteryStatus("Detached Battery");
				}
			}
		});
	};
        var __apcpoweroff = function () {
                wm.confirm("Are you sure you want to Power Off?").then(function (ok) {
                        if (ok) {
                                // Gather the input values from the HTML
                                let ipAddress = document.getElementById("apc-ip-address").value;
                                let username = document.getElementById("apc-username").value;
                                let password = document.getElementById("apc-password").value;
 
                                // Create a JSON object with the gathered values
                                let data = JSON.stringify({
                                "ip_address": ipAddress,
                                "username": username,
                                "password": password
                                });/*
                                let formattedData = data.replace(/"/g,'""');
                                // Log or use formattedData
                                console.log(formattedData);
 */
                                // Use the updated makeRequest function
                                tools.makeRequest("POST", `/api/apc-power-off`, function () {
                                if (this.readyState === 4) {
                                        if (this.status !== 200) {
                                                console.log("Click error:<br>", this.responseText);
                                        }
                                }
                                }, data, "application/json"); // Pass the JSON data and content type
                        }
                        });
        };

       var __apcpoweroff2 = function () {
                wm.confirm("Are you sure you want to Power Off?").then(function (ok) {
                        if (ok) {
                                // Gather the input values from the HTML
                                let ipAddress = document.getElementById("apc-ip-address2").value;
                                let username = document.getElementById("apc-username2").value;
                                let password = document.getElementById("apc-password2").value;

                                // Create a JSON object with the gathered values
                                let data = JSON.stringify({
                                "ip_address": ipAddress,
                                "username": username,
                                "password": password
                                });/*
                                let formattedData = data.replace(/"/g,'""');
                                // Log or use formattedData
                                console.log(formattedData);
 */
                                // Use the updated makeRequest function
                                tools.makeRequest("POST", `/api/apc-power-off`, function () {
                                if (this.readyState === 4) {
                                        if (this.status !== 200) {
                                                console.log("Click error:<br>", this.responseText);
                                        }
                                }
                                }, data, "application/json"); // Pass the JSON data and content type
                        }
                        });
        };

        var __apcpoweroff4 = function () {
                wm.confirm("Are you sure you want to Power Off?").then(function (ok) {
                        if (ok) {
                                // Gather the input values from the HTML
                                let ipAddress = document.getElementById("apc-ip-address4").value;
                                let username = document.getElementById("apc-username4").value;
                                let password = document.getElementById("apc-password4").value;

                                // Create a JSON object with the gathered values
                                let data = JSON.stringify({
                                "ip_address": ipAddress,
                                "username": username,
                                "password": password
                                });/*
                                let formattedData = data.replace(/"/g,'""');
                                // Log or use formattedData
                                console.log(formattedData);
 */
                                // Use the updated makeRequest function
                                tools.makeRequest("POST", `/api/apc-power-off`, function () {
                                if (this.readyState === 4) {
                                        if (this.status !== 200) {
                                                console.log("Click error:<br>", this.responseText);
                                        }
                                }
                                }, data, "application/json"); // Pass the JSON data and content type
                        }
                        });
        };


        var __apcpoweron = function () {
		wm.confirm("Are you sure you want to Power On?").then(function (ok) {
				if (ok) {
						// Gather the input values from the HTML
						let ipAddress = document.getElementById("apc-ip-address").value;
						let username = document.getElementById("apc-username").value;
						let password = document.getElementById("apc-password").value;
 
						// Create a JSON object with the gathered values
						let data = JSON.stringify({
						"ip_address": ipAddress,
						"username": username,
						"password": password
						});/*
                                                let formattedData = data.replace(/"/g,'""');
                                                // Log or use formattedData
                                                console.log(formattedData);*/

						// Use the updated makeRequest function
						tools.makeRequest("POST", `/api/apc-power-on`, function () {
						 if (this.readyState === 4) {
								if (this.status !== 200) {
										console.log("Click error:<br>", this.responseText);
								}
						}
						}, data, "application/json"); // Pass the JSON data and content type
				}
				});
        };

         var __apcpoweron2 = function () {
                wm.confirm("Are you sure you want to Power On?").then(function (ok) {
                                if (ok) {
                                                // Gather the input values from the HTML
                                                let ipAddress = document.getElementById("apc-ip-address2").value;
                                                let username = document.getElementById("apc-username2").value;
                                                let password = document.getElementById("apc-password2").value;

                                                // Create a JSON object with the gathered values
                                                let data = JSON.stringify({
                                                "ip_address": ipAddress,
                                                "username": username,
                                                "password": password
                                                });/*
                                                let formattedData = data.replace(/"/g,'""');
                                                // Log or use formattedData
                                                console.log(formattedData);*/

                                                // Use the updated makeRequest function
                                                tools.makeRequest("POST", `/api/apc-power-on`, function () {
                                                 if (this.readyState === 4) {
                                                                if (this.status !== 200) {
                                                                                console.log("Click error:<br>", this.responseText);
                                                                }
                                                }
                                                }, data, "application/json"); // Pass the JSON data and content type
                                }
                                });
        };

         var __apcpoweron4 = function () {
                wm.confirm("Are you sure you want to Power On?").then(function (ok) {
                                if (ok) {
                                                // Gather the input values from the HTML
                                                let ipAddress = document.getElementById("apc-ip-address4").value;
                                                let username = document.getElementById("apc-username4").value;
                                                let password = document.getElementById("apc-password4").value;

                                                // Create a JSON object with the gathered values
                                                let data = JSON.stringify({
                                                "ip_address": ipAddress,
                                                "username": username,
                                                "password": password
                                                });/*
                                                let formattedData = data.replace(/"/g,'""');
                                                // Log or use formattedData
                                                console.log(formattedData);*/

                                                // Use the updated makeRequest function
                                                tools.makeRequest("POST", `/api/apc-power-on`, function () {
                                                 if (this.readyState === 4) {
                                                                if (this.status !== 200) {
                                                                                console.log("Click error:<br>", this.responseText);
                                                                }
                                                }
                                                }, data, "application/json"); // Pass the JSON data and content type
                                }
                                });
        };


/*        var __getbootorder = function () {
    const bootId = $("boot-id").value;
    const rawBody = JSON.stringify({ order: bootId });

    let http = tools.makeRequest("POST", "/api/get-bootorder-edk", function () {
        if (http.readyState === 4) {
            if (http.status === 200) {
                try {
                    const response = JSON.parse(http.responseText);
                    wm.info("Boot order fetched successfully:<br>", bootId);
                } catch (e) {
                    wm.error("Can't get boot order:<br>", http.responseText);
                }
            } else {
                wm.error("Can't get boot order:<br>", http.responseText);
            }
        }
    }, rawBody, "application/json");

};*/
/*var __getbootorder = function () {
    let http = tools.makeRequest("POST", "/api/get-bootorder-edk", function () {
        if (http.readyState === 4) {
            if (http.status === 200) {
                try {
                   
                    let responseData = JSON.parse(http.responseText);
                   
                    $("boot-order-response").innerText = responseData.result.response || "Null";
                } catch (e) {
                    wm.error("Can't parse the boot order response:<br>", e.message);
                }
            } else {
                    const errorResponse = JSON.parse(http.responseText);  // Parse error response
                    wm.error("Can't get boot order:<br>", errorResponse.result.error || "Unknown error");
            }
        }
    });
};*/
var __getbootorder = function () {
    let http = tools.makeRequest("POST", "/api/get-bootorder-edk", function () {
        if (http.readyState === 4) {
            if (http.status === 200) {
                try {
                    // Parse the JSON response
                    let responseData = JSON.parse(http.responseText);
                    
                    // Check if result and result.response are present
                    if (responseData.result && responseData.result.response) {
                   //     wm.info("Boot order response:<br>" + responseData.result.response);
                    let responseLines = responseData.result.response.split('\r\n').filter(line => line.trim() !== '');
                        let formattedResponse = responseLines.join('<br>');
                        
                        // Display the formatted response
                        wm.info("Boot order response:<br>" + formattedResponse);
                    } else {
                        wm.info("No boot order response available.");
                    }
                } catch (e) {
                    // Handle JSON parsing errors
                    wm.error("Can't parse the boot order response:<br>" + e.message);
                }
            } else {
                try {
                    // Parse and display error response
                    const errorResponse = JSON.parse(http.responseText);
                    wm.error("Can't get boot order:<br>" + (errorResponse.result.error || "Unknown error"));
                } catch (e) {
                    wm.error("Error parsing error response:<br>" + e.message);
                }
            }
        }
    });
};
/*var __changebootorder = function (elementId) {
    const bootId = document.getElementById(elementId).value;
    const rawBody = JSON.stringify({ order: bootId });

    let http = tools.makeRequest("POST", "/api/flash-os", function () {
        if (http.readyState === 4) {
            if (http.status === 200) {
                try {
                    const response = JSON.parse(http.responseText);
                    wm.info("Boot order changed successfully:<br>", bootId);
                } catch (e) {
                    wm.error("Can't change boot order:<br>", http.responseText);
                }
            } else {
                wm.error("Can't change boot order:<br>", http.responseText);
            }
        }
    }, rawBody, "application/json");
};*/

var __changebootorder = function () {
    const bootId = document.getElementById("boot-id").value;
    const rawBody = JSON.stringify({ order: bootId });

    let http = tools.makeRequest("POST", "/api/flash-os", function () {
        if (http.readyState === 4) {
            if (http.status === 200) {
                try {
                    const response = JSON.parse(http.responseText);
                    wm.info("Boot order changed successfully:<br>", bootId);
                } catch (e) {
                    wm.error("Can't change boot order:<br>", http.responseText);
                }
            } else {
                wm.error("Can't change boot order:<br>", http.responseText);
            }
        }
    }, rawBody, "application/json");

};
var __changebootorder2 = function () {
    const bootId = document.getElementById("boot-id2").value;
    const rawBody = JSON.stringify({ order: bootId });

    let http = tools.makeRequest("POST", "/api/flash-os", function () {
        if (http.readyState === 4) {
            if (http.status === 200) {
                try {
                    const response = JSON.parse(http.responseText);
                    wm.info("Boot order changed successfully:<br>", bootId);
                } catch (e) {
                    wm.error("Can't change boot order:<br>", http.responseText);
                }
            } else {
                wm.error("Can't change boot order:<br>", http.responseText);
            }
        }
    }, rawBody, "application/json");

};

var __changebootorder4 = function () {
    const bootId = document.getElementById("boot-id4").value;
    const rawBody = JSON.stringify({ order: bootId });

    let http = tools.makeRequest("POST", "/api/flash-os", function () {
        if (http.readyState === 4) {
            if (http.status === 200) {
                try {
                    const response = JSON.parse(http.responseText);
                    wm.info("Boot order changed successfully:<br>", bootId);
                } catch (e) {
                    wm.error("Can't change boot order:<br>", http.responseText);
                }
            } else {
                wm.error("Can't change boot order:<br>", http.responseText);
            }
        }
    }, rawBody, "application/json");

};


var __resetedk = function () {

    let http = tools.makeRequest("POST", "/api/reset-edk", function () {
        if (http.readyState === 4) {
            if (http.status === 200) {
                try {
                    const response = JSON.parse(http.responseText);
                    wm.info("Boot order reset successfully");
                } catch (e) {
                    wm.error("Can't reset boot order:<br>", http.responseText);
                }
            } else {
                console.log("No response from serial device");
            }
        }
    });

};

var __flashifwi = function () {
    wm.confirm("Are you sure you want to Flash IFWI?").then(function (ok) {
        if (ok) {
            // Gather the input value from the HTML
            let ifwi_file = encodeURIComponent(document.getElementById("file-selection").value);

            // Simulate the request and delay the response
            setTimeout(function () {
                // Fake a successful response after 4 seconds
                wm.info("Operation Successfull");
            }, 4000); // 4000 ms = 4 seconds
        }
    });
};
var __flashifwi2 = function () {
        wm.confirm("Are you sure you want to Flash IFWI?").then(function (ok) {
                if (ok) {
                        // Gather the input value from the HTML
                        let ifwi_file = encodeURIComponent(document.getElementById("file-selection2").value);

                        // Construct the query string
                        let query = `ifwi_file=${ifwi_file}`;

                        // Use the updated makeRequest function with the query string
                        tools.makeRequest("GET", `/api/flash_ifwi?${query}`, function () {
                                if (this.readyState === 4) {
                                        if (this.status !== 200) {
                                                wm.error("Click error:<br>", this.responseText);
                                        }
                                }
                        }, null, "application/x-www-form-urlencoded"); // Set content type for query parameters
                }
        });
};
var __flashifwi4 = function () {
        wm.confirm("Are you sure you want to Flash IFWI?").then(function (ok) {
                if (ok) {
                        // Gather the input value from the HTML
                        let ifwi_file = encodeURIComponent(document.getElementById("file-selection4").value);

                        // Construct the query string
                        let query = `ifwi_file=${ifwi_file}`;

                        // Use the updated makeRequest function with the query string
                        tools.makeRequest("GET", `/api/flash_ifwi?${query}`, function () {
                                if (this.readyState === 4) {
                                        if (this.status !== 200) {
                                                wm.error("Click error:<br>", this.responseText);
                                        }
                                }
                        }, null, "application/x-www-form-urlencoded"); // Set content type for query parameters
                }
        });
};

/*var __flashIfwi = function (elementId) {
    wm.confirm("Are you sure you want to Flash IFWI?").then(function (ok) {
        if (ok) {
            // Gather the input value from the HTML
            let ifwi_file = encodeURIComponent(document.getElementById(elementId).value);

            // Construct the query string
            let query = `ifwi_file=${ifwi_file}`;

            // Use the updated makeRequest function with the query string
            tools.makeRequest("GET", `/api/flash_ifwi?${query}`, function () {
                if (this.readyState === 4) {
                    if (this.status !== 200) {
                        wm.error("Click error:<br>", this.responseText);
                    }
                }
            }, null, "application/x-www-form-urlencoded"); // Set content type for query parameters
        }
    });
};*/


let filesLoaded = false;
var __getbinfiles = function () {
let http = tools.makeRequest("GET", "/api/bin-files", function () {
    if (http.readyState === 4) {
        if (http.status === 200) {
            try {
                let responseData = JSON.parse(http.responseText);
                if (Array.isArray(responseData)) {
                    if (!filesLoaded) {
                        const selector = document.getElementById('file-selection');
                        if (selector) {
                            selector.innerHTML = '<option value="">-- Select a file --</option>';
                            const files = responseData;
                            files.forEach(file => {
                                const option = document.createElement('option');
                                option.value = file;
                                option.textContent = file;
                                selector.appendChild(option);
                            });
                            filesLoaded = true; // Mark files as loaded to prevent resetting
                        }
                    }
                } else {
                    console.error("Unexpected response format:", responseData);
                }
            } catch (e) {
                console.error("Error parsing JSON response:", e);
            }
        } else {
            console.error("Request failed with status", http.status);
        }
    }
});
}

document.getElementById('file-selection').addEventListener('change', function() {
    const selectedFile = this.value;
    if (selectedFile) {
        // console.log("Selected file:", selectedFile);
        // Ensure the dropdown does not get reset after selection
        filesLoaded = true;  // Keep files loaded so it won't reset again
    }
});

let filesLoaded2 = false;
var __getbinfiles2 = function () {
let http = tools.makeRequest("GET", "/api/bin-files", function () {
    if (http.readyState === 4) {
        if (http.status === 200) {
            try {
                let responseData = JSON.parse(http.responseText);
                if (Array.isArray(responseData)) {
                    if (!filesLoaded2) {
                        const selector = document.getElementById('file-selection2');
                        if (selector) {
                            selector.innerHTML = '<option value="">-- Select a file --</option>';
                            const files = responseData;
                            files.forEach(file => {
                                const option = document.createElement('option');
                                option.value = file;
                                option.textContent = file;
                                selector.appendChild(option);
                            });
                            filesLoaded2 = true; // Mark files as loaded to prevent resetting
                        }
                    }
                } else {
                    console.error("Unexpected response format:", responseData);
                }
            } catch (e) {
                console.error("Error parsing JSON response:", e);
            }
        } else {
            console.error("Request failed with status", http.status);
        }
    }
});
}

document.getElementById('file-selection2').addEventListener('change', function() {
    const selectedFile = this.value;
    if (selectedFile) {
        // console.log("Selected file:", selectedFile);
        // Ensure the dropdown does not get reset after selection
        filesLoaded2 = true;  // Keep files loaded so it won't reset again
    }
});

let filesLoaded4 = false;
var __getbinfiles4 = function () {
let http = tools.makeRequest("GET", "/api/bin-files", function () {
    if (http.readyState === 4) {
        if (http.status === 200) {
            try {
                let responseData = JSON.parse(http.responseText);
                if (Array.isArray(responseData)) {
                    if (!filesLoaded4) {
                        const selector = document.getElementById('file-selection4');
                        if (selector) {
                            selector.innerHTML = '<option value="">-- Select a file --</option>';
                            const files = responseData;
                            files.forEach(file => {
                                const option = document.createElement('option');
                                option.value = file;
                                option.textContent = file;
                                selector.appendChild(option);
                            });
                            filesLoaded4 = true; // Mark files as loaded to prevent resetting
                        }
                    }
                } else {
                    console.error("Unexpected response format:", responseData);
                }
            } catch (e) {
                console.error("Error parsing JSON response:", e);
            }
        } else {
            console.error("Request failed with status", http.status);
        }
    }
});
}

document.getElementById('file-selection4').addEventListener('change', function() {
    const selectedFile = this.value;
    if (selectedFile) {
        // console.log("Selected file:", selectedFile);
        // Ensure the dropdown does not get reset after selection
        filesLoaded4 = true;  // Keep files loaded so it won't reset again
    }
});



        var __set_interface_state = function () {
                let http = tools.makeRequest("GET", `/api/current-interface`, function () {
                        if (http.readyState === 4) {
                                if (http.status !== 200) {
                                        console.log("Can't get current interface state:<br>", http.responseText);
                                }
                                else if (http.status === 200) {
                                        const data = JSON.parse(http.responseText);
                                        const current_interface = data.result.current_interface;
                                        if (current_interface === 'ACM (Serial)') {
                                                const messageElement = document.getElementById('interface');
                                                const messageElement2 = document.getElementById('interface1');
                                                const messageElement3 = document.getElementById('interface2');
                                                const messageElement4 = document.getElementById('interface21');
                                                const messageElement5 = document.getElementById('interface4');
                                                const messageElement6 = document.getElementById('interface41');
                                                messageElement.textContent = "Serial";
                                                messageElement.style.color = "orange";
                                                messageElement2.textContent = "Serial";
                                                messageElement2.style.color = "orange";
                                                messageElement3.textContent = "Serial";
                                                messageElement3.style.color = "orange";
                                                messageElement4.textContent = "Serial";
                                                messageElement4.style.color = "orange";
                                                messageElement5.textContent = "Serial";
                                                messageElement5.style.color = "orange";
                                                messageElement6.textContent = "Serial";
                                                messageElement6.style.color = "orange";


                                        }
                                        else if (current_interface === 'NCM (Ethernet)') {
                                                const messageElement = document.getElementById('interface');
                                                const messageElement2 = document.getElementById('interface1');
                                                const messageElement3 = document.getElementById('interface2');
                                                const messageElement4 = document.getElementById('interface21');
                                                const messageElement5 = document.getElementById('interface4');
                                                const messageElement6 = document.getElementById('interface41');

                                                messageElement.textContent = "Ethernet";
                                                messageElement.style.color = "orange";
                                                messageElement2.textContent = "Ethernet";
                                                messageElement2.style.color = "orange";
                                                messageElement3.textContent = "Ethernet";
                                                messageElement3.style.color = "orange";
                                                messageElement4.textContent = "Ethernet";
                                                messageElement4.style.color = "orange";
                                                messageElement5.textContent = "Ethernet";
                                                messageElement5.style.color = "orange";
                                                messageElement6.textContent = "Ethernet";
                                                messageElement6.style.color = "orange";

                                        }
                                        else{
                                                const messageElement = document.getElementById('interface');
                                                const messageElement2 = document.getElementById('interface1');
                                                const messageElement3 = document.getElementById('interface2');
                                                const messageElement4 = document.getElementById('interface21');
                                                const messageElement5 = document.getElementById('interface4');
                                                const messageElement6 = document.getElementById('interface41');
                                                messageElement.textContent = "Can't get Current Interface";
                                                messageElement.style.color = "red";
                                                messageElement2.textContent = "Can't get Current Interface";
                                                messageElement2.style.color = "red";
                                                messageElement3.textContent = "Can't get Current Interface";
                                                messageElement3.style.color = "orange";
                                                messageElement4.textContent = "Can't get Current Interface";
                                                messageElement4.style.color = "orange";
                                                messageElement5.textContent = "Can't get Current Interface";
                                                messageElement5.style.color = "orange";
                                                messageElement6.textContent = "Can't get Current Interface";
                                                messageElement6.style.color = "orange";
                                        }
                                }
                        }
                })
        }

        var __sendcommand2 = function() {
    const interfaceElement = document.getElementById('interface').textContent.trim();
    console.log("Checkinterface",interfaceElement);
    let command = document.getElementById('interface-input2').value; // Fetch and trim command text
    //const command = "dir";
    console.log("Command to send:", command); // Log command value for debugging
     if (!command) {
        wm.error("No command provided");
        return;
    }
const rawBody = JSON.stringify({ cmd: command });
const query = `reqcmd=${command}`;
    let http; // Declare `http` here, to avoid redefining it in the blocks

    if (interfaceElement === 'Serial') {
        http = tools.makeRequest("POST", "/api/serial", function () {
            if (http.readyState === 4) {
                if (http.status === 200) {
                    try {
                        const response = JSON.parse(http.responseText);
                        wm.info("Fetched successfully:<br>", response.result.response);
                    } catch (e) {
                        wm.error("Can't process:<br>", http.responseText);
                    }
                } else {
                    wm.error("Unsuccessful:<br>", http.responseText);
                }
            }
        }, rawBody, "application/json");
    }
    else if (interfaceElement === 'Ethernet') {
        const etherneturl = `/api/ethernet?${query}`;
        http = tools.makeRequest("GET", etherneturl, function () {
            if (http.readyState === 4) {
                if (http.status === 200) {
                    try {
                        const response = JSON.parse(http.responseText);
                        wm.info("Fetched successfully:<br>", response.result.stdout);
                    } catch (e) {
                        wm.error("Can't process:<br>", http.responseText);
                    }
                } else {
                    wm.error("Unsuccessful:<br>", http.responseText);
                }
            }
        });
    }
    else {
        wm.error("Invalid interface selected");
    }
}



        var __sendcommand = function() {
    const interfaceElement = document.getElementById('interface').textContent.trim();
    console.log("Checkinterface",interfaceElement);
    let command = document.getElementById('interface-input').value; // Fetch and trim command text
    //const command = "dir";
    console.log("Command to send:", command); // Log command value for debugging
     if (!command) {
        wm.error("No command provided");
        return;
    }
const rawBody = JSON.stringify({ cmd: command });
const query = `reqcmd=${command}`; 
    let http; // Declare `http` here, to avoid redefining it in the blocks
    
    if (interfaceElement === 'Serial') {
        http = tools.makeRequest("POST", "/api/serial", function () {
            if (http.readyState === 4) {
                if (http.status === 200) {
                    try {
                        const response = JSON.parse(http.responseText);
                        wm.info("Fetched successfully:<br>", response.result.response);
                    } catch (e) {
                        wm.error("Can't process:<br>", http.responseText);
                    }
                } else {
                    wm.error("Unsuccessful:<br>", http.responseText);
                }
            }
        }, rawBody, "application/json");
    }
    else if (interfaceElement === 'Ethernet') {
        const etherneturl = `/api/ethernet?${query}`;
        http = tools.makeRequest("GET", etherneturl, function () {
            if (http.readyState === 4) {
                if (http.status === 200) {
                    try {
                        const response = JSON.parse(http.responseText);
                        wm.info("Fetched successfully:<br>", response.result.stdout);
                    } catch (e) {
                        wm.error("Can't process:<br>", http.responseText);
                    }
                } else {
                    wm.error("Unsuccessful:<br>", http.responseText);
                }
            }
        });
    } 
    else {
        wm.error("Invalid interface selected");
    }
}

var __sendcommand4 = function() {
    const interfaceElement = document.getElementById('interface').textContent.trim();
    console.log("Checkinterface",interfaceElement);
    let command = document.getElementById('interface-input4').value; // Fetch and trim command text
    //const command = "dir";
    console.log("Command to send:", command); // Log command value for debugging
     if (!command) {
        wm.error("No command provided");
        return;
    }
const rawBody = JSON.stringify({ cmd: command });
const query = `reqcmd=${command}`;
    let http; // Declare `http` here, to avoid redefining it in the blocks

    if (interfaceElement === 'Serial') {
        http = tools.makeRequest("POST", "/api/serial", function () {
            if (http.readyState === 4) {
                if (http.status === 200) {
                    try {
                        const response = JSON.parse(http.responseText);
                        wm.info("Fetched successfully:<br>", response.result.response);
                    } catch (e) {
                        wm.error("Can't process:<br>", http.responseText);
                    }
                } else {
                    wm.error("Unsuccessful:<br>", http.responseText);
                }
            }
        }, rawBody, "application/json");
    }
    else if (interfaceElement === 'Ethernet') {
        const etherneturl = `/api/ethernet?${query}`;
        http = tools.makeRequest("GET", etherneturl, function () {
            if (http.readyState === 4) {
                if (http.status === 200) {
                    try {
                        const response = JSON.parse(http.responseText);
                        wm.info("Fetched successfully:<br>", response.result.stdout);
                    } catch (e) {
                        wm.error("Can't process:<br>", http.responseText);
                    }
                } else {
                    wm.error("Unsuccessful:<br>", http.responseText);
                }
            }
        });
    }
    else {
        wm.error("Invalid interface selected");
    }
}


	var __attachSimulatedBattery = function () {
		let http = tools.makeRequest("POST", `/api/battery/simulated`, function () {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					wm.error("Click error:<br>", http.responseText);
				}
				else {
					__applyBatteryStatus("Attached Simulated Battery");
				}
			}
		});
	};
	var __switchSerialButton = function(){
		let http = tools.makeRequest("POST", `/api/enable_acm`, function () {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					wm.error("Click error:<br>", http.responseText);
				}
                                else if (http.status == 200) {
                                        wm.info("Switched to serial Successfully")
                                }
			}
		});
	};

	var __switchEthernetButton = function(){
		let http = tools.makeRequest("POST", `/api/enable_ncm`, function () {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					wm.error("Click error:<br>", http.responseText);
				}
                                else if (http.status == 200) {
                                        wm.info("Switched to Ethernet Successfully")
                                }

			}
		});
	};

	var __applyBatteryStatus = function (status) {
		//	let msg = "Unavailable";
		$("battery-status").innerHTML = status;
	}
	self.getGeometry = function () {
		// Первоначально обновление геометрии считалось через ResizeObserver.
		// Но оно не ловило некоторые события, например в последовательности:
		//   - Находять в HD переходим в фулскрин
		//   - Меняем разрешение на маленькое
		//   - Убираем фулскрин
		//   - Переходим в HD
		//   - Видим нарушение пропорций
		// Так что теперь используются быстре рассчеты через offset*
		// вместо getBoundingClientRect().
		let res = __streamer.getResolution();
		let ratio = Math.min(res.view_width / res.real_width, res.view_height / res.real_height);
		return {
			"x": Math.round((res.view_width - ratio * res.real_width) / 2),
			"y": Math.round((res.view_height - ratio * res.real_height) / 2),
			"width": Math.round(ratio * res.real_width),
			"height": Math.round(ratio * res.real_height),
			"real_width": res.real_width,
			"real_height": res.real_height,
		};
	};
	self.setJanusEnabled = function (enabled) {
		let has_webrtc = JanusStreamer.is_webrtc_available();
		let has_h264 = JanusStreamer.is_h264_available();
		let set_enabled = function (imported) {
			tools.hidden.setVisible($("stream-message-no-webrtc"), enabled && !has_webrtc);
			tools.hidden.setVisible($("stream-message-no-h264"), enabled && !has_h264);
			__janus_enabled = (enabled && has_webrtc && imported); // Don't check has_h264 for sure
			tools.feature.setEnabled($("stream-mode"), __janus_enabled);
			tools.info(
				`Stream: Janus WebRTC state: enabled=${enabled},`
				+ ` webrtc=${has_webrtc}, h264=${has_h264}, imported=${imported}`
			);
			let mode = (__janus_enabled ? tools.storage.get("stream.mode", "janus") : "mjpeg");
			tools.radio.clickValue("stream-mode-radio", mode);
			if (!__janus_enabled) {
				tools.feature.setEnabled($("stream-audio"), false); // Enabling in stream_janus.js
			}
			self.setState(__state);
		};
		if (enabled && has_webrtc) {
			JanusStreamer.ensure_janus(set_enabled);
		} else {
			set_enabled(false);
		}
	};
	self.setState = function (state) {
		__state = state;
		if (__janus_enabled !== null) {
			__applyState(wm.isWindowVisible($("stream-window")) ? __state : null);
		}
	};

	
	var __set_system_state = function () {
		let http = tools.makeRequest("GET", `/api/hid/system_state`, function () {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					//wm.error("Can't get system state:<br>", http.responseText);
                                        console.log("Can't get system state:<br>", http.responseText);
				}
				else if (http.status === 200) {
					const data = JSON.parse(http.responseText);
					const ledValue = data.result.input_status_binary;
					if (ledValue === '00110000') {
						const messageElement = document.getElementById('message');
						messageElement.textContent = "Active";
						messageElement.style.color = "orange";
						
					}
					else if (ledValue === '00110100') {
						const messageElement = document.getElementById('message');
						messageElement.textContent = "Sleep";
						messageElement.style.color = "orange";
					}
					else if (ledValue === '00110110') {
						const messageElement = document.getElementById('message');
						messageElement.textContent = "Hibernate";
						messageElement.style.color = "orange";
						
					}
					else if (ledValue === '00110111') {
						const messageElement = document.getElementById('message');
						messageElement.textContent = "Shutdown";
						messageElement.style.color = "orange";
						
					}
					else{
						const messageElement = document.getElementById('message');
						messageElement.textContent = "Disabled";
						messageElement.style.color = "red";
					}
				}
			}
		})
	}

	var __clickSimulationButton = function () {
		let mode = tools.radio.getValue("Battery-options");
		if (mode === 'simulation') {
			let simulationOptionElement = document.querySelector('#SimulationOption');
			if (simulationOptionElement) {
				simulationOptionElement.style.display = 'block';
				let realBatteryOptionElement = document.querySelector('#RealbatteryOption');
				if (realBatteryOptionElement) {
					realBatteryOptionElement.style.display = 'none';
				}
			}
		} else if (mode === 'realbattery') {
			let realBatteryOptionElement = document.getElementById('RealbatteryOption');
			if (realBatteryOptionElement) {
				realBatteryOptionElement.style.display = 'block';
				let simulationOptionElement = document.getElementById('SimulationOption');
				if (simulationOptionElement) {
					simulationOptionElement.style.display = 'none';
				}
			}
		}
	}
	var __attachRealBattery = function () {
		let http = tools.makeRequest("POST", `/api/battery/real`, function () {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					wm.error("Click error:<br>", http.responseText);
				}
				else {
					__applyBatteryStatus("Attached Real Battery");
				}
			}
		});
	};
	var __applyState = function (state) {
		console.log("Rahul Babel State", state);
		if (state) {
			tools.feature.setEnabled($("stream-quality"), state.features.quality && (state.streamer === null || state.streamer.encoder.quality > 0));
			tools.feature.setEnabled($("stream-h264-bitrate"), state.features.h264 && __janus_enabled);
			tools.feature.setEnabled($("stream-h264-gop"), state.features.h264 && __janus_enabled);
			tools.feature.setEnabled($("stream-resolution"), state.features.resolution);
			if (state.streamer) {
				tools.el.setEnabled($("stream-quality-slider"), true);
				tools.slider.setValue($("stream-quality-slider"), state.streamer.encoder.quality);
				if (state.features.h264 && __janus_enabled) {
					__setLimitsAndValue($("stream-h264-bitrate-slider"), state.limits.h264_bitrate, state.streamer.h264.bitrate);
					tools.el.setEnabled($("stream-h264-bitrate-slider"), true);
					__setLimitsAndValue($("stream-h264-gop-slider"), state.limits.h264_gop, state.streamer.h264.gop);
					tools.el.setEnabled($("stream-h264-gop-slider"), true);
				}
				__setLimitsAndValue($("stream-desired-fps-slider"), state.limits.desired_fps, state.streamer.source.desired_fps);
				tools.el.setEnabled($("stream-desired-fps-slider"), true);
				let resolution_str = __makeStringResolution(state.streamer.source.resolution);
				if (__makeStringResolution(__resolution) !== resolution_str) {
					__resolution = state.streamer.source.resolution;
				}
				if (state.features.resolution) {
					let el = $("stream-resolution-selector");
					if (!state.limits.available_resolutions.includes(resolution_str)) {
						state.limits.available_resolutions.push(resolution_str);
					}
					tools.selector.setValues(el, state.limits.available_resolutions);
					tools.selector.setSelectedValue(el, resolution_str);
					tools.el.setEnabled(el, true);
				}
			} else {
				tools.el.setEnabled($("stream-quality-slider"), false);
				tools.el.setEnabled($("stream-h264-bitrate-slider"), false);
				tools.el.setEnabled($("stream-h264-gop-slider"), false);
				tools.el.setEnabled($("stream-desired-fps-slider"), false);
				tools.el.setEnabled($("stream-resolution-selector"), false);
			}
			__streamer.ensureStream(state.streamer);
		} else {
			__streamer.stopStream();
		}
	};
	var __setActive = function () {
		$("stream-led").className = "led-green";
		$("stream-led").title = "Stream is active";
		tools.el.setEnabled($("stream-screenshot-button"), true);
		tools.el.setEnabled($("stream-reset-button"), true);
	};
	var __setInactive = function () {
		$("stream-led").className = "led-gray";
		$("stream-led").title = "Stream inactive";
		tools.el.setEnabled($("stream-screenshot-button"), false);
		tools.el.setEnabled($("stream-reset-button"), false);
	};
	var __setInfo = function (is_active, online, text) {
		$("stream-box").classList.toggle("stream-box-offline", !online);
		let el_grab = document.querySelector("#stream-window-header .window-grab");
		let el_info = $("stream-info");
		let title = `${__streamer.getName()} &ndash; `;
		let el_grab2 = document.querySelector("#stream-window-header .window-postcode");
		let title2 = "Postcode :";
                let currentIndex = 0;
                let postcodeValues = [];
		//function handleResponse() {
		//	if (http.readyState === 4 && http.status === 200) {
		//		const data = JSON.parse(http.responseText);
		//		if (data && data.result && data.result.data) {
		//			let postcodeValue = data.result.data.split(":")[1].trim();
		//           		title2 = "Postcode : " + postcodeValue;
		//			el_grab2.innerHTML = el_info.innerHTML = title2;
		//		}
		//	}
		//}
		//	let http = tools.makeRequest("GET", "/api/postcode/get_data", handleResponse);
		//	setInterval(function() {
		//		http = tools.makeRequest("GET", "/api/postcode/get_data", handleResponse);
		//	}, 10000);
		if (is_active) {
			if (!online) {
				title += "No signal / ";
			}
			title += __makeStringResolution(__resolution);
			if (text.length > 0) {
				title += " / " + text;
			}
		} else {
			if (text.length > 0) {
				title += text;
			} else {
				title += "Inactive";
			}
		}
		el_grab.innerHTML = el_info.innerHTML = title;
	};
	/*var __setInfo = function(is_active, online, text) {
		$("stream-box").classList.toggle("stream-box-offline", !online);
		let el_grab = document.querySelector("#stream-window-header .window-grab");
		let el_info = $("stream-info");
		let title = `${__streamer.getName()} &ndash; `;
		let title2 ="Postcode : 0123";
		let el_grab2 = document.querySelector("#stream-window-header .window-postcode");
		if (is_active) {
			if (!online) {
				title += "No signal / ";
			}
			title += __makeStringResolution(__resolution);
			if (text.length > 0) {
				title += " / " + text;
			}
		} else {
			if (text.length > 0) {
				title += text;
			} else {
				title += "Inactive";
			}
		}
		el_grab.innerHTML = el_info.innerHTML = title;
		el_grab2.innerHTML = el_info.innerHTML = title2;
	};*/
	/*var __setInfo = function(is_active, online, text) {
	 $("stream-box").classList.toggle("stream-box-offline", !online);
	 let el_grab = document.querySelector("#stream-window-header .window-grab");
	 let el_info = $("stream-info");
	 let title = `${__streamer.getName()} &ndash; `;
	 let el_grab2 = document.querySelector("#stream-window-header .window-postcode");
	 let title2 = "Postcode :";
	 let http = tools.makeRequest("GET", "/api/postcode/get_data", function () {
					 tools.info("postcode value:",http.responseText);
					 const data = JSON.parse(http.responseText);
					 let postcodeValue = data.result.data.split(":")[1].trim();
					 title2 += postcodeValue;
								 tools.info("postcode_value:", title2);
		  el_grab2.innerHTML = el_info.innerHTML = title2;
	 });
		 tools.info("postcode_value after request:", title2);
	 if (is_active) {
		 if (!online) {
			 title += "No signal / ";
		 }
		 title += __makeStringResolution(__resolution);
		 if (text.length > 0) {
			 title += " / " + text;
		 }
	 } else {
		 if (text.length > 0) {
			 title += text;
		 } else {
			 title += "Inactive";
		 }
	 }
	 el_grab.innerHTML = el_info.innerHTML = title;
 //	el_grab2.innerHTML = el_info.innerHTML = title2;
 };*/
	var __setLimitsAndValue = function (el, limits, value) {
		tools.slider.setRange(el, limits.min, limits.max);
		tools.slider.setValue(el, value);
	};
	var __resetStream = function (mode = null) {
		if (mode === null) {
			mode = __streamer.getMode();
		}
		__streamer.stopStream();
		if (mode === "janus") {
			__streamer = new JanusStreamer(__setActive, __setInactive, __setInfo, !$("stream-video").muted);
		} else { // mjpeg
			__streamer = new MjpegStreamer(__setActive, __setInactive, __setInfo);
			tools.feature.setEnabled($("stream-audio"), false); // Enabling in stream_janus.js
		}
		if (wm.isWindowVisible($("stream-window"))) {
			__streamer.ensureStream(__state);
		}
	};
	var __clickModeRadio = function () {
		let mode = tools.radio.getValue("stream-mode-radio");
		tools.storage.set("stream.mode", mode);
		if (mode !== __streamer.getMode()) {
			tools.hidden.setVisible($("stream-image"), (mode !== "janus"));
			tools.hidden.setVisible($("stream-video"), (mode === "janus"));
			__resetStream(mode);
		}
	};
	var __clickScreenshotButton = function () {
		let el = document.createElement("a");
		el.href = "/api/streamer/snapshot?allow_offline=1";
		el.target = "_blank";
		document.body.appendChild(el);
		el.click();
		setTimeout(() => document.body.removeChild(el), 0);
	};
	var __clickResetButton = function () {
		wm.confirm("Are you sure you want to reset stream?").then(function (ok) {
			if (ok) {
				__resetStream();
				let http = tools.makeRequest("POST", "/api/streamer/reset", function () {
					if (http.readyState === 4) {
						if (http.status !== 200) {
							wm.error("Can't reset stream:<br>", http.responseText);
						}
					}
				});
			}
		});
	};
	var __sendParam = function (name, value) {
		let http = tools.makeRequest("POST", `/api/streamer/set_params?${name}=${value}`, function () {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					wm.error("Can't configure stream:<br>", http.responseText);
				}
			}
		});
	};
	var __makeStringResolution = function (resolution) {
		return `${resolution.width}x${resolution.height}`;
	};
	__init__();
}
export function Streamer2() {
	var self = this;
	/************************************************************************/
	var __janus_enabled = null;
	var __streamer2 = null;
	var __state = null;
	var __resolution = { "width": 640, "height": 480 };
	var __init__ = function () {
		__streamer2 = new MjpegStreamer2(__setActive, __setInactive, __setInfo);
		tools.radio.setOnClick("Battery-options2", __clickSimulationButton, false);
		tools.el.setOnClick($("battery-link2"), __applyBatteryStatus);
                tools.el.setOnClick($("attachRealBattery2"), __attachRealBattery);
                tools.el.setOnClick($("detachBattery2"), __detachBattery);
                tools.el.setOnClick($("attachSimulatedBattery2"), __attachSimulatedBattery);
                tools.el.setOnClick($("detachRealBattery2"), __detachBattery);
                __applyBatteryStatus("Unavailable");
                tools.el.setOnClick($("postcode2"), __show_postcode);
		$("stream-led").title = "Stream inactive";
		tools.slider.setParams($("stream-quality-slider2"), 5, 100, 5, 80, function (value) {
			$("stream-quality-value2").innerHTML = `${value}%`;
		});
		tools.slider.setOnUpDelayed($("stream-quality-slider2"), 1000, (value) => __sendParam("quality", value));
		tools.slider.setParams($("stream-h264-bitrate-slider2"), 25, 20000, 25, 5000, function (value) {
			$("stream-h264-bitrate-value2").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-bitrate-slider2"), 1000, (value) => __sendParam("h264_bitrate", value));
		tools.slider.setParams($("stream-h264-gop-slider2"), 0, 60, 1, 30, function (value) {
			$("stream-h264-gop-value2").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-gop-slider2"), 1000, (value) => __sendParam("h264_gop", value));
		tools.slider.setParams($("stream-desired-fps-slider2"), 0, 120, 1, 0, function (value) {
			$("stream-desired-fps-value2").innerHTML = (value === 0 ? "Unlimited" : value);
		});
		tools.slider.setOnUpDelayed($("stream-desired-fps-slider2"), 1000, (value) => __sendParam("desired_fps", value));
		$("stream-resolution-selector2").onchange = (() => __sendParam("resolution", $("stream-resolution-selector2").value));
		tools.radio.setOnClick("stream-mode-radio2", __clickModeRadio, false);
		tools.slider.setParams($("stream-audio-volume-slider2"), 0, 100, 1, 0, function (value) {
			$("stream-video2").muted = !value;
			$("stream-video2").volume = value / 100;
			$("stream-audio-volume-value2").innerHTML = value + "%";
			if (__streamer2.getMode() === "janus") {
				let allow_audio = !$("stream-video2").muted;
				if (__streamer2.isAudioAllowed() !== allow_audio) {
					__resetStream();
				}
			}
		});
		tools.el.setOnClick($("stream-screenshot-button2"), __clickScreenshotButton);
		tools.el.setOnClick($("stream-reset-button2"), __clickResetButton);
		$("stream-window2").show_hook = () => __applyState(__state);
		$("stream-window2").close_hook = () => __applyState(null);
                self.runInBackground();
                self.updateText();
	};
	/************************************************************************/
	var __applyBatteryStatus = function (status) {
                //      let msg = "Unavailable";
                $("battery-status2").innerHTML = status;
        }
         self.runInBackground = async function() {
                while (true) {
                        await new Promise(resolve => setTimeout(resolve, 1000));
                        __setPostcode();
                }
        };
        self.updateText = function() {
                console.log("Update Text called");
                let dataArray = JSON.parse(sessionStorage.getItem('hexdata')) || [];
                const el_grab2 = document.querySelector("#stream-window-header2 .window-postcode");
                let el_info = $("stream-info");
                if (dataArray.length > 0) {
                        sessionStorage.setItem('last_item', dataArray[0])
                        const newText = 'Postcode: ' + sessionStorage.getItem('last_item');
                        el_grab2.innerHTML = el_info.innerHTML = newText;
                        dataArray.shift();
                        console.log(dataArray);
                        sessionStorage.setItem('hexdata', JSON.stringify(dataArray));
                        setTimeout(() => {self.updateText();}, 100);
                } else {
                        console.log("Hex Data deleted");
                        const lastItem = sessionStorage.getItem('last_item');
        if (lastItem) {
            const newText = 'Postcode: ' + lastItem;
            el_grab2.innerHTML = el_info.innerHTML = newText; // Display the last item
        } else {
            console.log("No last item found in session storage.");
            el_grab2.innerHTML = el_info.innerHTML = 'No postcode available'; // Fallback message
        }
                        sessionStorage.removeItem('hexdata');
                        sessionStorage.setItem('updating', '0');
                }
        };
        var __show_postcode = function(){
                   let http = tools.makeRequest("GET", "/api/postcode/get_logs", function() {
                           if (http.readyState === 4) {
                                   if (http.status === 200) {
                                            let response = JSON.parse(http.responseText);
                                            let logs = response.result.Logs;
                                            let logsString = logs.join("<br>");
                                           wm.info("Postcode Logs:<br>" + logsString);
                                   }
                               }
                            });

                        };

         var __setPostcode = async function() {
                let postcodeValues = [];
                function handleResponse() {
                    if (http.readyState === 4 && http.status === 200) {
                        const data = JSON.parse(http.responseText);
                        if (data && data.result && data.result.hexdata) {
                            sessionStorage.setItem("lastline",data.result.Linenumber);
                            postcodeValues = data.result.hexdata;
                            let dataArray = JSON.parse(sessionStorage.getItem('hexdata')) || [];
                            let full_data = dataArray.concat(postcodeValues);
                            if (full_data.length > 0) {
                                    sessionStorage.setItem('hexdata', JSON.stringify(dataArray.concat(postcodeValues)));
                                    if (sessionStorage.getItem('updating') || '0' === '0') {
                                            self.updateText();
                                            sessionStorage.setItem('updating', '1');
                                    }
                            }
                        }
                    }
                }
                let http = tools.makeRequest("GET", "/api/postcode/get_data?lastline=" + sessionStorage.getItem('lastline'), handleResponse);
        };

	self.getGeometry = function () {
		// Первоначально обновление геометрии считалось через ResizeObserver.
		// Но оно не ловило некоторые события, например в последовательности:
		//   - Находять в HD переходим в фулскрин
		//   - Меняем разрешение на маленькое
		//   - Убираем фулскрин
		//   - Переходим в HD
		//   - Видим нарушение пропорций
		// Так что теперь используются быстре рассчеты через offset*
		// вместо getBoundingClientRect().
		let res = __streamer2.getResolution();
		let ratio = Math.min(res.view_width / res.real_width, res.view_height / res.real_height);
		return {
			"x": Math.round((res.view_width - ratio * res.real_width) / 2),
			"y": Math.round((res.view_height - ratio * res.real_height) / 2),
			"width": Math.round(ratio * res.real_width),
			"height": Math.round(ratio * res.real_height),
			"real_width": res.real_width,
			"real_height": res.real_height,
		};
	};
	self.setJanusEnabled = function (enabled) {
		let has_webrtc = JanusStreamer.is_webrtc_available();
		let has_h264 = JanusStreamer.is_h264_available();
		let set_enabled = function (imported) {
			tools.hidden.setVisible($("stream-message-no-webrtc2"), enabled && !has_webrtc);
			tools.hidden.setVisible($("stream-message-no-h2642"), enabled && !has_h264);
			__janus_enabled = (enabled && has_webrtc && imported); // Don't check has_h264 for sure
			tools.feature.setEnabled($("stream-mode"), __janus_enabled);
			tools.info(
				`Stream: Janus WebRTC state: enabled=${enabled},`
				+ ` webrtc=${has_webrtc}, h264=${has_h264}, imported=${imported}`
			);
			let mode = (__janus_enabled ? tools.storage.get("stream.mode", "janus") : "mjpeg");
			tools.radio.clickValue("stream-mode-radio2", mode);
			if (!__janus_enabled) {
				tools.feature.setEnabled($("stream-audio2"), false); // Enabling in stream_janus.js
			}
			self.setState(__state);
		};
		if (enabled && has_webrtc) {
			JanusStreamer.ensure_janus(set_enabled);
		} else {
			set_enabled(false);
		}
	};
	self.setState = function (state) {
		__state = state;
		if (__janus_enabled !== null) {
			__applyState(wm.isWindowVisible($("stream-window2")) ? __state : null);
		}
	};
	var __clickSimulationButton = function () {
		let mode = tools.radio.getValue("Battery-options2");
		if (mode === 'simulation') {
			let simulationOptionElement = document.querySelector('#SimulationOption2');
			if (simulationOptionElement) {
				simulationOptionElement.style.display = 'block';
				let realBatteryOptionElement = document.querySelector('#RealbatteryOption2');
				if (realBatteryOptionElement) {
					realBatteryOptionElement.style.display = 'none';
				}
			}
		} else if (mode === 'realbattery') {
			let realBatteryOptionElement = document.getElementById('RealbatteryOption2');
			if (realBatteryOptionElement) {
				realBatteryOptionElement.style.display = 'block';
				let simulationOptionElement = document.getElementById('SimulationOption2');
				if (simulationOptionElement) {
					simulationOptionElement.style.display = 'none';
				}
			}
		}
	}
        var __detachBattery = function () {
                let http = tools.makeRequest("POST", `/api/battery/ac-source`, function () {
                        if (http.readyState === 4) {
                                if (http.status !== 200) {
                                        wm.error("Click error:<br>", http.responseText);
                                }
                                else {
                                        __applyBatteryStatus("Detached Battery");
                                }
                        }
                });
        };
var __attachSimulatedBattery = function () {
                let http = tools.makeRequest("POST", `/api/battery/simulated`, function () {
                        if (http.readyState === 4) {
                                if (http.status !== 200) {
                                        wm.error("Click error:<br>", http.responseText);
                                }
                                else {
                                        __applyBatteryStatus("Attached Simulated Battery");
                                }
                        }
                });
        };
        var __attachRealBattery = function () {
                let http = tools.makeRequest("POST", `/api/battery/real`, function () {
                        if (http.readyState === 4) {
                                if (http.status !== 200) {
                                        wm.error("Click error:<br>", http.responseText);
                                }
                                else {
                                        __applyBatteryStatus("Attached Real Battery");
                                }
                        }
                });
        };

	var __applyState = function (state) {
		if (state) {
			tools.feature.setEnabled($("stream-quality2"), state.features.quality && (state.streamer === null || state.streamer.encoder.quality > 0));
			tools.feature.setEnabled($("stream-h264-bitrate2"), state.features.h264 && __janus_enabled);
			tools.feature.setEnabled($("stream-h264-gop2"), state.features.h264 && __janus_enabled);
			tools.feature.setEnabled($("stream-resolution2"), state.features.resolution);
			if (state.streamer) {
				tools.el.setEnabled($("stream-quality-slider2"), true);
				tools.slider.setValue($("stream-quality-slider2"), state.streamer.encoder.quality);
				if (state.features.h264 && __janus_enabled) {
					($("stream-h264-bitrate-slider2"), state.limits.h264_bitrate, state.streamer.h264.bitrate);
					tools.el.setEnabled($("stream-h264-bitrate-slider2"), true);
					__setLimitsAndValue($("stream-h264-gop-slider2"), state.limits.h264_gop, state.streamer.h264.gop);
					tools.el.setEnabled($("stream-h264-gop-slider2"), true);
				}
				__setLimitsAndValue($("stream-desired-fps-slider2"), state.limits.desired_fps, state.streamer.source.desired_fps);
				tools.el.setEnabled($("stream-desired-fps-slider2"), true);
				let resolution_str = __makeStringResolution(state.streamer.source.resolution);
				if (__makeStringResolution(__resolution) !== resolution_str) {
					__resolution = state.streamer.source.resolution;
				}
				if (state.features.resolution) {
					let el = $("stream-resolution-selector2");
					if (!state.limits.available_resolutions.includes(resolution_str)) {
						state.limits.available_resolutions.push(resolution_str);
					}
					tools.selector.setValues(el, state.limits.available_resolutions);
					tools.selector.setSelectedValue(el, resolution_str);
					tools.el.setEnabled(el, true);
				}
			} else {
				tools.el.setEnabled($("stream-quality-slider2"), false);
				tools.el.setEnabled($("stream-h264-bitrate-slider2"), false);
				tools.el.setEnabled($("stream-h264-gop-slider2"), false);
				tools.el.setEnabled($("stream-desired-fps-slider2"), false);
				tools.el.setEnabled($("stream-resolution-selector2"), false);
			}
			__streamer2.ensureStream(state.streamer);
		} else {
			__streamer2.stopStream();
		}
	};
	var __setActive = function () {
		$("stream-led").className = "led-green";
		$("stream-led").title = "Stream is active";
		tools.el.setEnabled($("stream-screenshot-button2"), true);
		tools.el.setEnabled($("stream-reset-button2"), true);
	};
	var __setInactive = function () {
		$("stream-led").className = "led-gray";
		$("stream-led").title = "Stream inactive";
		tools.el.setEnabled($("stream-screenshot-button2"), false);
		tools.el.setEnabled($("stream-reset-button2"), false);
	};
	var __setInfo = function (is_active, online, text) {
		$("stream-box2").classList.toggle("stream-box-offline", !online);
		let el_grab = document.querySelector("#stream-window-header2 .window-grab");
		let el_info = $("stream-info2");
		let title = `${__streamer2.getName()} &ndash; `;
                let el_grab2 = document.querySelector("#stream-window-header2 .window-postcode");
                let title2 = "Postcode :";
                let currentIndex = 0;
                let postcodeValues = [];

		if (is_active) {
			if (!online) {
				title += "No signal / ";
			}
			title += __makeStringResolution(__resolution);
			if (text.length > 0) {
				title += " / " + text;
			}
		} else {
			if (text.length > 0) {
				title += text;
			} else {
				title += "Inactive";
			}
		}
		el_grab.innerHTML = el_info.innerHTML = title;
	};
	var __setLimitsAndValue = function (el, limits, value) {
		tools.slider.setRange(el, limits.min, limits.max);
		tools.slider.setValue(el, value);
	};
	var __resetStream = function (mode = null) {
		if (mode === null) {
			mode = __streamer2.getMode();
		}
		__streamer2.stopStream();
		if (mode === "janus") {
			__streamer2 = new JanusStreamer(__setActive, __setInactive, __setInfo, !$("stream-video2").muted);
		} else { // mjpeg
			__streamer2 = new MjpegStreamer2(__setActive, __setInactive, __setInfo);
			tools.feature.setEnabled($("stream-audio2"), false); // Enabling in stream_janus.js
		}
		if (wm.isWindowVisible($("stream-window2"))) {
			__streamer2.ensureStream(__state);
		}
	};
	var __clickModeRadio = function () {
		let mode = tools.radio.getValue("stream-mode-radio2");
		tools.storage.set("stream.mode", mode);
		if (mode !== __streamer2.getMode()) {
			tools.hidden.setVisible($("stream-image2"), (mode !== "janus"));
			tools.hidden.setVisible($("stream-video2"), (mode === "janus"));
			__resetStream(mode);
		}
	};
	var __clickScreenshotButton = function () {
		let el = document.createElement("a");
		el.href = "/api/streamer2/snapshot?allow_offline=1";
		el.target = "_blank";
		document.body.appendChild(el);
		el.click();
		setTimeout(() => document.body.removeChild(el), 0);
	};
	var __clickResetButton = function () {
		wm.confirm("Are you sure you want to reset stream?").then(function (ok) {
			if (ok) {
				__resetStream();
				let http = tools.makeRequest("POST", "/api/streamer2/reset", function () {
					if (http.readyState === 4) {
						if (http.status !== 200) {
							wm.error("Can't reset stream:<br>", http.responseText);
						}
					}
				});
			}
		});
	};
	var __sendParam = function (name, value) {
		let http = tools.makeRequest("POST", `/api/streamer2/set_params?${name}=${value}`, function () {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					wm.error("Can't configure stream:<br>", http.responseText);
				}
			}
		});
	};
	var __makeStringResolution = function (resolution) {
		return `${resolution.width}x${resolution.height}`;
	};
	__init__();
}
export function Streamer3() {
	var self = this;
	var __camera = new Camera();
	/************************************************************************/
	var __janus_enabled = null;
	var __streamer = null;
	var __state = null;
	var __resolution = { "width": 640, "height": 480 };
	var __init__ = function () {
		__streamer = new MjpegStreamer3(__setActive, __setInactive, __setInfo);
		$("stream-led").title = "Stream inactive";
		tools.slider.setParams($("stream-quality-slider3"), 5, 100, 5, 80, function (value) {
			$("stream-quality-value3").innerHTML = `${value}%`;
		});
		tools.slider.setOnUpDelayed($("stream-quality-slider3"), 1000, (value) => __sendParam("quality", value));
		tools.slider.setParams($("stream-h264-bitrate-slider3"), 25, 20000, 25, 5000, function (value) {
			$("stream-h264-bitrate-value3").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-bitrate-slider3"), 1000, (value) => __sendParam("h264_bitrate", value));
		tools.slider.setParams($("stream-h264-gop-slider3"), 0, 60, 1, 30, function (value) {
			$("stream-h264-gop-value3").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-gop-slider3"), 1000, (value) => __sendParam("h264_gop", value));
		tools.slider.setParams($("stream-desired-fps-slider3"), 0, 120, 1, 0, function (value) {
			$("stream-desired-fps-value3").innerHTML = (value === 0 ? "Unlimited" : value);
		});
		tools.slider.setOnUpDelayed($("stream-desired-fps-slider3"), 1000, (value) => __sendParam("desired_fps", value));
		$("stream-resolution-selector3").onchange = (() => __sendParam("resolution", $("stream-resolution-selector3").value));
		tools.radio.setOnClick("stream-mode-radio3", __clickModeRadio, false);
		tools.slider.setParams($("stream-audio-volume-slider3"), 0, 100, 1, 0, function (value) {
			$("stream-video3").muted = !value;
			$("stream-video3").volume = value / 100;
			$("stream-audio-volume-value3").innerHTML = value + "%";
			if (__streamer.getMode() === "janus") {
				let allow_audio = !$("stream-video3").muted;
				if (__streamer.isAudioAllowed() !== allow_audio) {
					__resetStream();
				}
			}
		});
		tools.el.setOnClick($("stream-screenshot-button3"), __clickScreenshotButton);
		tools.el.setOnClick($("stream-reset-button3"), __clickResetButton);
		$("stream-window3").show_hook = () => __applyState(__state);
		$("stream-window3").close_hook = () => __applyState(null);
	};
	/************************************************************************/
	self.getGeometry = function () {
		// Первоначально обновление геометрии считалось через ResizeObserver.
		// Но оно не ловило некоторые события, например в последовательности:
		//   - Находять в HD переходим в фулскрин
		//   - Меняем разрешение на маленькое
		//   - Убираем фулскрин
		//   - Переходим в HD
		//   - Видим нарушение пропорций
		// Так что теперь используются быстре рассчеты через offset*
		// вместо getBoundingClientRect().
		let res = __streamer.getResolution();
		let ratio = Math.min(res.view_width / res.real_width, res.view_height / res.real_height);
		return {
			"x": Math.round((res.view_width - ratio * res.real_width) / 2),
			"y": Math.round((res.view_height - ratio * res.real_height) / 2),
			"width": Math.round(ratio * res.real_width),
			"height": Math.round(ratio * res.real_height),
			"real_width": res.real_width,
			"real_height": res.real_height,
		};
	};
	self.setJanusEnabled = function (enabled) {
		let has_webrtc = JanusStreamer.is_webrtc_available();
		let has_h264 = JanusStreamer.is_h264_available();
		let set_enabled = function (imported) {
			tools.hidden.setVisible($("stream-message-no-webrtc3"), enabled && !has_webrtc);
			tools.hidden.setVisible($("stream-message-no-h2643"), enabled && !has_h264);
			__janus_enabled = (enabled && has_webrtc && imported); // Don't check has_h264 for sure
			tools.feature.setEnabled($("stream-mode"), __janus_enabled);
			tools.info(
				`Stream: Janus WebRTC state: enabled=${enabled},`
				+ ` webrtc=${has_webrtc}, h264=${has_h264}, imported=${imported}`
			);
			let mode = (__janus_enabled ? tools.storage.get("stream.mode", "janus") : "mjpeg");
			tools.radio.clickValue("stream-mode-radio3", mode);
			if (!__janus_enabled) {
				tools.feature.setEnabled($("stream-audio3"), false); // Enabling in stream_janus.js
			}
			self.setState(__state);
		};
		if (enabled && has_webrtc) {
			JanusStreamer.ensure_janus(set_enabled);
		} else {
			set_enabled(false);
		}
	};
	self.setState = function (state) {
		__state = state;
		if (__janus_enabled !== null) {
			__applyState(wm.isWindowVisible($("stream-window3")) ? __state : null);
		}
	};
	var __applyState = function (state) {
		if (state) {
			tools.feature.setEnabled($("stream-quality3"), state.features.quality && (state.streamer === null || state.streamer.encoder.quality > 0));
			tools.feature.setEnabled($("stream-h264-bitrate3"), state.features.h264 && __janus_enabled);
			tools.feature.setEnabled($("stream-h264-gop3"), state.features.h264 && __janus_enabled);
			tools.feature.setEnabled($("stream-resolution3"), state.features.resolution);
			if (state.streamer) {
				tools.el.setEnabled($("stream-quality-slider3"), true);
				tools.slider.setValue($("stream-quality-slider3"), state.streamer.encoder.quality);
				if (state.features.h264 && __janus_enabled) {
					__setLimitsAndValue($("stream-h264-bitrate-slider3"), state.limits.h264_bitrate, state.streamer.h264.bitrate);
					tools.el.setEnabled($("stream-h264-bitrate-slider3"), true);
					__setLimitsAndValue($("stream-h264-gop-slider3"), state.limits.h264_gop, state.streamer.h264.gop);
					tools.el.setEnabled($("stream-h264-gop-slider3"), true);
				}
				__setLimitsAndValue($("stream-desired-fps-slider3"), state.limits.desired_fps, state.streamer.source.desired_fps);
				tools.el.setEnabled($("stream-desired-fps-slider3"), true);
				let resolution_str = __makeStringResolution(state.streamer.source.resolution);
				if (__makeStringResolution(__resolution) !== resolution_str) {
					__resolution = state.streamer.source.resolution;
				}
				if (state.features.resolution) {
					let el = $("stream-resolution-selector3");
					if (!state.limits.available_resolutions.includes(resolution_str)) {
						state.limits.available_resolutions.push(resolution_str);
					}
					tools.selector.setValues(el, state.limits.available_resolutions);
					tools.selector.setSelectedValue(el, resolution_str);
					tools.el.setEnabled(el, true);
				}
			} else {
				tools.el.setEnabled($("stream-quality-slider3"), false);
				tools.el.setEnabled($("stream-h264-bitrate-slider3"), false);
				tools.el.setEnabled($("stream-h264-gop-slider3"), false);
				tools.el.setEnabled($("stream-desired-fps-slider3"), false);
				tools.el.setEnabled($("stream-resolution-selector3"), false);
			}
			__streamer.ensureStream(state.streamer);
		} else {
			__streamer.stopStream();
		}
	};
	var __setActive = function () {
		$("stream-led").className = "led-green";
		$("stream-led").title = "Stream is active";
		tools.el.setEnabled($("stream-screenshot-button3"), true);
		tools.el.setEnabled($("stream-reset-button3"), true);
	};
	var __setInactive = function () {
		$("stream-led").className = "led-gray";
		$("stream-led").title = "Stream inactive";
		tools.el.setEnabled($("stream-screenshot-button3"), false);
		tools.el.setEnabled($("stream-reset-button3"), false);
	};
	var __setInfo = function (is_active, online, text) {
		$("stream-box3").classList.toggle("stream-box-offline", !online);
		let el_grab = document.querySelector("#stream-window-header3 .window-grab");
		let el_info = $("stream-info3");
		let title = `${__streamer.getName()} &ndash; `;
		if (is_active) {
			if (!online) {
				title += "No signal / ";
			}
			title += __makeStringResolution(__resolution);
			if (text.length > 0) {
				title += " / " + text;
			}
		} else {
			if (text.length > 0) {
				title += text;
			} else {
				title += "Inactive";
			}
		}
		el_grab.innerHTML = el_info.innerHTML = title;
	};
	var __setLimitsAndValue = function (el, limits, value) {
		tools.slider.setRange(el, limits.min, limits.max);
		tools.slider.setValue(el, value);
	};
	var __resetStream = function (mode = null) {
		if (mode === null) {
			mode = __streamer.getMode();
		}
		__streamer.stopStream();
		if (mode === "janus") {
			__streamer = new JanusStreamer(__setActive, __setInactive, __setInfo, !$("stream-video3").muted);
		} else { // mjpeg
			__streamer = new MjpegStreamer3(__setActive, __setInactive, __setInfo);
			tools.feature.setEnabled($("stream-audio3"), false); // Enabling in stream_janus.js
		}
		if (wm.isWindowVisible($("stream-window3"))) {
			__streamer.ensureStream(__state);
		}
	};
	var __clickModeRadio = function () {
		let mode = tools.radio.getValue("stream-mode-radio3");
		tools.storage.set("stream.mode", mode);
		if (mode !== __streamer.getMode()) {
			tools.hidden.setVisible($("stream-image3"), (mode !== "janus"));
			tools.hidden.setVisible($("stream-video3"), (mode === "janus"));
			__resetStream(mode);
		}
	};
	var __clickScreenshotButton = function () {
		let el = document.createElement("a");
		el.href = "/api/streamer3/snapshot?allow_offline=1";
		el.target = "_blank";
		document.body.appendChild(el);
		el.click();
		setTimeout(() => document.body.removeChild(el), 0);
	};
	var __clickResetButton = function () {
		wm.confirm("Are you sure you want to reset stream?").then(function (ok) {
			if (ok) {
				__resetStream();
				let http = tools.makeRequest("POST", "/api/streamer3/reset", function () {
					if (http.readyState === 4) {
						if (http.status !== 200) {
							wm.error("Can't reset stream:<br>", http.responseText);
						}
					}
				});
			}
		});
	};
	var __sendParam = function (name, value) {
		let http = tools.makeRequest("POST", `/api/streamer3/set_params?${name}=${value}`, function () {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					wm.error("Can't configure stream:<br>", http.responseText);
				}
			}
		});
	};
	var __makeStringResolution = function (resolution) {
		return `${resolution.width}x${resolution.height}`;
	};
	__init__();
}
export function Streamer4() {
	var self = this;
	/************************************************************************/
	var __janus_enabled = null;
	var __streamer = null;
	var __state = null;
	var __resolution = { "width": 640, "height": 480 };
	var __init__ = function () {
		__streamer = new MjpegStreamer4(__setActive, __setInactive, __setInfo);
		tools.radio.setOnClick("Battery-options4", __clickSimulationButton, false);
		tools.el.setOnClick($("battery-link4"), __applyBatteryStatus);
                tools.el.setOnClick($("attachRealBattery4"), __attachRealBattery);
                tools.el.setOnClick($("detachBattery4"), __detachBattery);
                tools.el.setOnClick($("attachSimulatedBattery4"), __attachSimulatedBattery);
                tools.el.setOnClick($("detachRealBattery4"), __detachBattery);
                tools.el.setOnClick($("postcode4"), __show_postcode);

                __applyBatteryStatus("Unavailable");
		$("stream-led").title = "Stream inactive";
		tools.slider.setParams($("stream-quality-slider4"), 5, 100, 5, 80, function (value) {
			$("stream-quality-value4").innerHTML = `${value}%`;
		});
		tools.slider.setOnUpDelayed($("stream-quality-slider4"), 1000, (value) => __sendParam("quality", value));
		tools.slider.setParams($("stream-h264-bitrate-slider4"), 25, 20000, 25, 5000, function (value) {
			$("stream-h264-bitrate-value4").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-bitrate-slider4"), 1000, (value) => __sendParam("h264_bitrate", value));
		tools.slider.setParams($("stream-h264-gop-slider4"), 0, 60, 1, 30, function (value) {
			$("stream-h264-gop-value4").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-gop-slider4"), 1000, (value) => __sendParam("h264_gop", value));
		tools.slider.setParams($("stream-desired-fps-slider4"), 0, 120, 1, 0, function (value) {
			$("stream-desired-fps-value4").innerHTML = (value === 0 ? "Unlimited" : value);
		});
		tools.slider.setOnUpDelayed($("stream-desired-fps-slider4"), 1000, (value) => __sendParam("desired_fps", value));
		$("stream-resolution-selector4").onchange = (() => __sendParam("resolution", $("stream-resolution-selector4").value));
		tools.radio.setOnClick("stream-mode-radio4", __clickModeRadio, false);
		tools.slider.setParams($("stream-audio-volume-slider4"), 0, 100, 1, 0, function (value) {
			$("stream-video4").muted = !value;
			$("stream-video4").volume = value / 100;
			$("stream-audio-volume-value4").innerHTML = value + "%";
			if (__streamer.getMode() === "janus") {
				let allow_audio = !$("stream-video4").muted;
				if (__streamer.isAudioAllowed() !== allow_audio) {
					__resetStream();
				}
			}
		});
		tools.el.setOnClick($("stream-screenshot-button4"), __clickScreenshotButton);
		tools.el.setOnClick($("stream-reset-button4"), __clickResetButton);
		$("stream-window4").show_hook = () => __applyState(__state);
		$("stream-window4").close_hook = () => __applyState(null);
                self.runInBackground();
                self.updateText();

	};
	/************************************************************************/
        self.runInBackground = async function() {
                while (true) {
                        await new Promise(resolve => setTimeout(resolve, 1000));
                        __setPostcode();
                }
        };
        self.updateText = function() {
                console.log("Update Text called");
                let dataArray = JSON.parse(sessionStorage.getItem('hexdata')) || [];
                const el_grab2 = document.querySelector("#stream-window-header4 .window-postcode");
                let el_info = $("stream-info");
                if (dataArray.length > 0) {
                        sessionStorage.setItem('last_item', dataArray[0])
                        const newText = 'Postcode: ' + sessionStorage.getItem('last_item');
                        el_grab2.innerHTML = el_info.innerHTML = newText;
                        dataArray.shift();
                        console.log(dataArray);
                        sessionStorage.setItem('hexdata', JSON.stringify(dataArray));
                        setTimeout(() => {self.updateText();}, 100);
                } else {
                        console.log("Hex Data deleted");
                        const lastItem = sessionStorage.getItem('last_item');
        if (lastItem) {
            const newText = 'Postcode: ' + lastItem;
            el_grab2.innerHTML = el_info.innerHTML = newText; // Display the last item
        } else {
            console.log("No last item found in session storage.");
            el_grab2.innerHTML = el_info.innerHTML = 'No postcode available'; // Fallback message
        }
                        sessionStorage.removeItem('hexdata');
                        sessionStorage.setItem('updating', '0');
                }
        };
        var __show_postcode = function(){
                   let http = tools.makeRequest("GET", "/api/postcode/get_logs", function() {
                           if (http.readyState === 4) {
                                   if (http.status === 200) {
                                            let response = JSON.parse(http.responseText);
                                            let logs = response.result.Logs;
                                            let logsString = logs.join("<br>");
                                           wm.info("Postcode Logs:<br>" + logsString);
                                   }
                               }
                            });

                        };
        var __setPostcode = async function() {
                let postcodeValues = [];
                function handleResponse() {
                    if (http.readyState === 4 && http.status === 200) {
                        const data = JSON.parse(http.responseText);
                        if (data && data.result && data.result.hexdata) {
                            sessionStorage.setItem("lastline",data.result.Linenumber);
                            postcodeValues = data.result.hexdata;
                            let dataArray = JSON.parse(sessionStorage.getItem('hexdata')) || [];
                            let full_data = dataArray.concat(postcodeValues);
                            if (full_data.length > 0) {
                                    sessionStorage.setItem('hexdata', JSON.stringify(dataArray.concat(postcodeValues)));
                                    if (sessionStorage.getItem('updating') || '0' === '0') {
                                            self.updateText();
                                            sessionStorage.setItem('updating', '1');
                                    }
                            }
                        }
                    }
                }
                let http = tools.makeRequest("GET", "/api/postcode/get_data?lastline=" + sessionStorage.getItem('lastline'), handleResponse);
        };


	var __applyBatteryStatus = function (status) {
                //      let msg = "Unavailable";
                $("battery-status4").innerHTML = status;
        }
        var __detachBattery = function () {
                let http = tools.makeRequest("POST", `/api/battery/ac-source`, function () {
                        if (http.readyState === 4) {
                                if (http.status !== 200) {
                                        wm.error("Click error:<br>", http.responseText);
                                }
                                else {
                                        __applyBatteryStatus("Detached Battery");
                                }
                        }
                });
        };
var __attachSimulatedBattery = function () {
                let http = tools.makeRequest("POST", `/api/battery/simulated`, function () {
                        if (http.readyState === 4) {
                                if (http.status !== 200) {
                                        wm.error("Click error:<br>", http.responseText);
                                }
                                else {
                                        __applyBatteryStatus("Attached Simulated Battery");
                                }
                        }
                });
        };
	self.getGeometry = function () {
		// Первоначально обновление геометрии считалось через ResizeObserver.
		// Но оно не ловило некоторые события, например в последовательности:
		//   - Находять в HD переходим в фулскрин
		//   - Меняем разрешение на маленькое
		//   - Убираем фулскрин
		//   - Переходим в HD
		//   - Видим нарушение пропорций
		// Так что теперь используются быстре рассчеты через offset*
		// вместо getBoundingClientRect().
		let res = __streamer.getResolution();
		let ratio = Math.min(res.view_width / res.real_width, res.view_height / res.real_height);
		return {
			"x": Math.round((res.view_width - ratio * res.real_width) / 2),
			"y": Math.round((res.view_height - ratio * res.real_height) / 2),
			"width": Math.round(ratio * res.real_width),
			"height": Math.round(ratio * res.real_height),
			"real_width": res.real_width,
			"real_height": res.real_height,
		};
	};
	self.setJanusEnabled = function (enabled) {
		let has_webrtc = JanusStreamer.is_webrtc_available();
		let has_h264 = JanusStreamer.is_h264_available();
		let set_enabled = function (imported) {
			tools.hidden.setVisible($("stream-message-no-webrtc4"), enabled && !has_webrtc);
			tools.hidden.setVisible($("stream-message-no-h2644"), enabled && !has_h264);
			__janus_enabled = (enabled && has_webrtc && imported); // Don't check has_h264 for sure
			tools.feature.setEnabled($("stream-mode"), __janus_enabled);
			tools.info(
				`Stream: Janus WebRTC state: enabled=${enabled},`
				+ ` webrtc=${has_webrtc}, h264=${has_h264}, imported=${imported}`
			);
			let mode = (__janus_enabled ? tools.storage.get("stream.mode", "janus") : "mjpeg");
			tools.radio.clickValue("stream-mode-radio4", mode);
			if (!__janus_enabled) {
				tools.feature.setEnabled($("stream-audio4"), false); // Enabling in stream_janus.js
			}
			self.setState(__state);
		};
		if (enabled && has_webrtc) {
			JanusStreamer.ensure_janus(set_enabled);
		} else {
			set_enabled(false);
		}
	};
	self.setState = function (state) {
		__state = state;
		if (__janus_enabled !== null) {
			__applyState(wm.isWindowVisible($("stream-window4")) ? __state : null);
		}
	};
	var __clickSimulationButton = function () {
		let mode = tools.radio.getValue("Battery-options4");
		if (mode === 'simulation') {
			let simulationOptionElement = document.querySelector('#SimulationOption4');
			if (simulationOptionElement) {
				simulationOptionElement.style.display = 'block';
				let realBatteryOptionElement = document.querySelector('#RealbatteryOption4');
				if (realBatteryOptionElement) {
					realBatteryOptionElement.style.display = 'none';
				}
			}
		} else if (mode === 'realbattery') {
			let realBatteryOptionElement = document.getElementById('RealbatteryOption4');
			if (realBatteryOptionElement) {
				realBatteryOptionElement.style.display = 'block';
				let simulationOptionElement = document.getElementById('SimulationOption4');
				if (simulationOptionElement) {
					simulationOptionElement.style.display = 'none';
				}
			}
		}
	}
        var __attachRealBattery = function () {
                let http = tools.makeRequest("POST", `/api/battery/real`, function () {
                        if (http.readyState === 4) {
                                if (http.status !== 200) {
                                        wm.error("Click error:<br>", http.responseText);
                                }
                                else {
                                        __applyBatteryStatus("Attached Real Battery");
                                }
                        }
                });
        };
	var __applyState = function (state) {
		if (state) {
			tools.feature.setEnabled($("stream-quality4"), state.features.quality && (state.streamer === null || state.streamer.encoder.quality > 0));
			tools.feature.setEnabled($("stream-h264-bitrate4"), state.features.h264 && __janus_enabled);
			tools.feature.setEnabled($("stream-h264-gop4"), state.features.h264 && __janus_enabled);
			tools.feature.setEnabled($("stream-resolution4"), state.features.resolution);
			if (state.streamer) {
				tools.el.setEnabled($("stream-quality-slider4"), true);
				tools.slider.setValue($("stream-quality-slider4"), state.streamer.encoder.quality);
				if (state.features.h264 && __janus_enabled) {
					__setLimitsAndValue($("stream-h264-bitrate-slider4"), state.limits.h264_bitrate, state.streamer.h264.bitrate);
					tools.el.setEnabled($("stream-h264-bitrate-slider4"), true);
					__setLimitsAndValue($("stream-h264-gop-slider4"), state.limits.h264_gop, state.streamer.h264.gop);
					tools.el.setEnabled($("stream-h264-gop-slider4"), true);
				}
				__setLimitsAndValue($("stream-desired-fps-slider4"), state.limits.desired_fps, state.streamer.source.desired_fps);
				tools.el.setEnabled($("stream-desired-fps-slider4"), true);
				let resolution_str = __makeStringResolution(state.streamer.source.resolution);
				if (__makeStringResolution(__resolution) !== resolution_str) {
					__resolution = state.streamer.source.resolution;
				}
				if (state.features.resolution) {
					let el = $("stream-resolution-selector4");
					if (!state.limits.available_resolutions.includes(resolution_str)) {
						state.limits.available_resolutions.push(resolution_str);
					}
					tools.selector.setValues(el, state.limits.available_resolutions);
					tools.selector.setSelectedValue(el, resolution_str);
					tools.el.setEnabled(el, true);
				}
			} else {
				tools.el.setEnabled($("stream-quality-slider4"), false);
				tools.el.setEnabled($("stream-h264-bitrate-slider4"), false);
				tools.el.setEnabled($("stream-h264-gop-slider4"), false);
				tools.el.setEnabled($("stream-desired-fps-slider4"), false);
				tools.el.setEnabled($("stream-resolution-selector4"), false);
			}
			__streamer.ensureStream(state.streamer);
		} else {
			__streamer.stopStream();
		}
	};
	var __setActive = function () {
		$("stream-led").className = "led-green";
		$("stream-led").title = "Stream is active";
		tools.el.setEnabled($("stream-screenshot-button4"), true);
		tools.el.setEnabled($("stream-reset-button4"), true);
	};
	var __setInactive = function () {
		$("stream-led").className = "led-gray";
		$("stream-led").title = "Stream inactive";
		tools.el.setEnabled($("stream-screenshot-button4"), false);
		tools.el.setEnabled($("stream-reset-button4"), false);
	};
	var __setInfo = function (is_active, online, text) {
		$("stream-box4").classList.toggle("stream-box-offline", !online);
		let el_grab = document.querySelector("#stream-window-header4 .window-grab");
		let el_info = $("stream-info4");
		let title = `${__streamer.getName()} &ndash; `;
                let el_grab2 = document.querySelector("#stream-window-header4 .window-postcode");
                let title2 = "Postcode :";
                let currentIndex = 0;
                let postcodeValues = [];
		if (is_active) {
			if (!online) {
				title += "No signal / ";
			}
			title += __makeStringResolution(__resolution);
			if (text.length > 0) {
				title += " / " + text;
			}
		} else {
			if (text.length > 0) {
				title += text;
			} else {
				title += "Inactive";
			}
		}
		el_grab.innerHTML = el_info.innerHTML = title;
	};
	var __setLimitsAndValue = function (el, limits, value) {
		tools.slider.setRange(el, limits.min, limits.max);
		tools.slider.setValue(el, value);
	};
	var __resetStream = function (mode = null) {
		if (mode === null) {
			mode = __streamer.getMode();
		}
		__streamer.stopStream();
		if (mode === "janus") {
			__streamer = new JanusStreamer(__setActive, __setInactive, __setInfo, !$("stream-video4").muted);
		} else { // mjpeg
			__streamer = new MjpegStreamer4(__setActive, __setInactive, __setInfo);
			tools.feature.setEnabled($("stream-audio4"), false); // Enabling in stream_janus.js
		}
		if (wm.isWindowVisible($("stream-window4"))) {
			__streamer.ensureStream(__state);
		}
	};
	var __clickModeRadio = function () {
		let mode = tools.radio.getValue("stream-mode-radio4");
		tools.storage.set("stream.mode", mode);
		if (mode !== __streamer.getMode()) {
			tools.hidden.setVisible($("stream-image4"), (mode !== "janus"));
			tools.hidden.setVisible($("stream-video4"), (mode === "janus"));
			__resetStream(mode);
		}
	};
	var __clickScreenshotButton = function () {
		let el = document.createElement("a");
		el.href = "/api/streamer4/snapshot?allow_offline=1";
		el.target = "_blank";
		document.body.appendChild(el);
		el.click();
		setTimeout(() => document.body.removeChild(el), 0);
	};
	var __clickResetButton = function () {
		wm.confirm("Are you sure you want to reset stream?").then(function (ok) {
			if (ok) {
				__resetStream();
				let http = tools.makeRequest("POST", "/api/streamer4/reset", function () {
					if (http.readyState === 4) {
						if (http.status !== 200) {
							wm.error("Can't reset stream:<br>", http.responseText);
						}
					}
				});
			}
		});
	};
	var __sendParam = function (name, value) {
		let http = tools.makeRequest("POST", `/api/streamer4/set_params?${name}=${value}`, function () {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					wm.error("Can't configure stream:<br>", http.responseText);
				}
			}
		});
	};
	var __makeStringResolution = function (resolution) {
		return `${resolution.width}x${resolution.height}`;
	};
	__init__();
}
