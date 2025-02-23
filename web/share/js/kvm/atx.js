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


import {tools, $} from "../tools.js";
import {wm} from "../wm.js";

export function Atx4(__recorder) {
    var self = this;

    

    var __init__ = function() {
            $("atx-power-led4").title = "Power Led";
            $("atx-hdd-led4").title = "Disk Activity Led";

            tools.storage.bindSimpleSwitch($("atx-ask-switch4"), "atx.ask", true);

            // for (let args of [
            //         ["atx-power-button", "power", "Are you sure you want to press the power button?"],
            //         ["atx-power-button-long", "power_long", `
            //                 Are you sure you want to long press the power button?<br>
            //                 Warning! This could cause data loss on the server.
            //         `],
            //         ["atx-reset-button", "reset", `
            //                 Are you sure you want to press the reset button?<br>
            //                 Warning! This could case data loss on the server.
            //         `],
            // ]) {
            //         tools.el.setOnClick($(args[0]), () => __clickButton(args[1], args[2]));
            // }

            for (let args of [
                ["atx-power-button", "power", "Are you sure you want to perform the power operation?"],
                ["atx-reset-button", "reset", "Are you sure you want to perform the reset operation?"],
            ]) {
                tools.el.setOnClick($(args[0]), () => __clickButton(args[1], args[2]));
            }
    };

    

    self.setState = function(state) {
            let buttons_enabled = false;
            if (state) {
                    tools.feature.setEnabled($("atx-dropdown4"), state.enabled);
                    $("atx-power-led4").className = (state.busy ? "led-yellow" : (state.leds.power ? "led-green" : "led-gray"));
                    $("atx-hdd-led4").className = (state.leds.hdd ? "led-red" : "led-gray");
                    buttons_enabled = !state.busy;
            } else {
                    $("atx-power-led4").className = "led-gray";
                    $("atx-hdd-led4").className = "led-gray";
            }
            // for (let id of ["atx-power-button4", "atx-power-button-long4", "atx-reset-button4"]) {
            //         tools.el.setEnabled($(id), buttons_enabled);
            // }

            for (let id of ["atx-power-button", "atx-reset-button"]) {
                tools.el.setEnabled($(id), buttons_enabled);
            }
    };

    var __clickButton = function(button, confirm_msg) {
            let click_button = function() {
                let http = tools.makeRequest("GET", `/api/atx/${button}`, function() {
                            if (http.readyState === 4) {
                                    if (http.status === 409) {
                                            wm.error("Performing another ATX operation for other client.<br>Please try again later");
                                    } else if (http.status !== 200) {
                                            wm.error("Click error:<br>", http.responseText);
                                    }
                            }
                    });
                    __recorder.recordAtxButtonEvent(button);
            };

            if ($("atx-ask-switch4").checked) {
                    wm.confirm(confirm_msg).then(function(ok) {
                            if (ok) {
                                    click_button();
                            }
                    });
            } else {
                    click_button();
            }
    };

    __init__();
}                                                                                                                                                                                                                        
export function Atx(__recorder) {
	var self = this;

	

	var __init__ = function() {
		$("atx-power-led").title = "Power Led";
		$("atx-hdd-led").title = "Disk Activity Led";

		tools.storage.bindSimpleSwitch($("atx-ask-switch"), "atx.ask", true);

		for (let args of [
			["atx-power-button4", "power", "Are you sure you want to press the power button?"],
			["atx-reset-button4", "reset", "Are you sure you want to press the reset button?"],
		]) {
			tools.el.setOnClick($(args[0]), () => __clickButton(args[1], args[2]));
		}
	};

	

	self.setState = function(state) {
		let buttons_enabled = false;
		if (state) {
			tools.feature.setEnabled($("atx-dropdown"), state.enabled);
			$("atx-power-led").className = (state.busy ? "led-yellow" : (state.leds.power ? "led-green" : "led-gray"));
			$("atx-hdd-led").className = (state.leds.hdd ? "led-red" : "led-gray");
			buttons_enabled = !state.busy;
		} else {
			$("atx-power-led").className = "led-gray";
			$("atx-hdd-led").className = "led-gray";
		}
		for (let id of ["atx-power-button4", "atx-reset-button4"]) {
			tools.el.setEnabled($(id), buttons_enabled);
		}
	};

	var __clickButton = function(button, confirm_msg) {
		let click_button = function() {
			let http = tools.makeRequest("GET", `/api/atx/${button}`, function() {
				if (http.readyState === 4) {
					if (http.status === 409) {
						wm.error("Performing another ATX operation for other client.<br>Please try again later");
					} else if (http.status !== 200) {
						wm.error("Click error:<br>", http.responseText);
					}
				}
			});
			__recorder.recordAtxButtonEvent(button);
		};

		if ($("atx-ask-switch").checked) {
			wm.confirm(confirm_msg).then(function(ok) {
				if (ok) {
					click_button();
				}
			});
		} else {
			click_button();
		}
	};

	__init__();
}

export function Atx2(__recorder) {
	var self = this;

	/************************************************************************/

	var __init__ = function() {
		$("atx-power-led2").title = "Power Led";
		$("atx-hdd-led2").title = "Disk Activity Led";

		tools.storage.bindSimpleSwitch($("atx-ask-switch2"), "atx.ask", true);

		for (let args of [
			["atx-power-button2", "power", "Are you sure you want to press the power button?"],
			["atx-reset-button2", "reset", "Are you sure you want to press the reset button?"],
		]) {
			tools.el.setOnClick($(args[0]), () => __clickButton(args[1], args[2]));
		}
	};

	/************************************************************************/

	self.setState = function(state) {
		let buttons_enabled = false;
		if (state) {
			tools.feature.setEnabled($("atx-dropdown2"), state.enabled);
			$("atx-power-led2").className = (state.busy ? "led-yellow" : (state.leds.power ? "led-green" : "led-gray"));
			$("atx-hdd-led2").className = (state.leds.hdd ? "led-red" : "led-gray");
			buttons_enabled = !state.busy;
		} else {
			$("atx-power-led2").className = "led-gray";
			$("atx-hdd-led2").className = "led-gray";
		}
		for (let id of ["atx-power-button2", "atx-reset-button2"]) {
			tools.el.setEnabled($(id), buttons_enabled);
		}
	};

	var __clickButton = function(button, confirm_msg) {
		let click_button = function() {
			let http = tools.makeRequest("GET", `/api/atx/${button}`, function() {
				if (http.readyState === 4) {
					if (http.status === 409) {
						wm.error("Performing another ATX operation for other client.<br>Please try again later");
					} else if (http.status !== 200) {
						wm.error("Click error:<br>", http.responseText);
					}
				}
			});
			__recorder.recordAtxButtonEvent(button);
		};

		if ($("atx-ask-switch2").checked) {
			wm.confirm(confirm_msg).then(function(ok) {
				if (ok) {
					click_button();
				}
			});
		} else {
			click_button();
		}
	};

	__init__();
}

/*export function Atx4(__recorder) {
	var self = this;

	

	var __init__ = function() {
		$("atx-power-led4").title = "Power Led";
		$("atx-hdd-led4").title = "Disk Activity Led";

		tools.storage.bindSimpleSwitch($("atx-ask-switch"), "atx.ask", true);

		for (let args of [
			["atx-power-button", "power", "Are you sure you want to press the power button?"],
			["atx-power-button-long", "power_long", `
				Are you sure you want to long press the power button?<br>
				Warning! This could cause data loss on the server.
			`],
			["atx-reset-button", "reset", `
				Are you sure you want to press the reset button?<br>
				Warning! This could case data loss on the server.
			`],
		]) {
			tools.el.setOnClick($(args[0]), () => __clickButton(args[1], args[2]));
		}
	};

	

	self.setState = function(state) {
		let buttons_enabled = false;
		if (state) {
			tools.feature.setEnabled($("atx-dropdown4"), state.enabled);
			$("atx-power-led4").className = (state.busy ? "led-yellow" : (state.leds.power ? "led-green" : "led-gray"));
			$("atx-hdd-led4").className = (state.leds.hdd ? "led-red" : "led-gray");
			buttons_enabled = !state.busy;
		} else {
			$("atx-power-led4").className = "led-gray";
			$("atx-hdd-led4").className = "led-gray";
		}
		for (let id of ["atx-power-button4", "atx-power-button-long4", "atx-reset-button4"]) {
			tools.el.setEnabled($(id), buttons_enabled);
		}
	};

	var __clickButton = function(button, confirm_msg) {
		let click_button = function() {
			let http = tools.makeRequest("POST", `/api/atx/click?button=${button}`, function() {
				if (http.readyState === 4) {
					if (http.status === 409) {
						wm.error("Performing another ATX operation for other client.<br>Please try again later");
					} else if (http.status !== 200) {
						wm.error("Click error:<br>", http.responseText);
					}
				}
			});
			__recorder.recordAtxButtonEvent(button);
		};

		if ($("atx-ask-switch4").checked) {
			wm.confirm(confirm_msg).then(function(ok) {
				if (ok) {
					click_button();
				}
			});
		} else {
			click_button();
		}
	};

	__init__();
}
*/
