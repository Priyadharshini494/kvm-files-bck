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

import {JanusStreamer} from "./stream_janus.js";
import {MjpegStreamer} from "./stream_mjpeg.js";
import {MjpegStreamer2} from "./stream_mjpeg.js";
import {MjpegStreamer3} from "./stream_mjpeg.js";
import {MjpegStreamer4} from "./stream_mjpeg.js";


export function Streamer() {
	var self = this;

	/************************************************************************/

	var __janus_enabled = null;
	var __streamer = null;

	var __state = null;
	var __resolution = {"width": 640, "height": 480};

	var __init__ = function() {
		__streamer = new MjpegStreamer(__setActive, __setInactive, __setInfo);

		$("stream-led").title = "Stream inactive";

		tools.slider.setParams($("stream-quality-slider"), 5, 100, 5, 80, function(value) {
			$("stream-quality-value").innerHTML = `${value}%`;
		});
		tools.slider.setOnUpDelayed($("stream-quality-slider"), 1000, (value) => __sendParam("quality", value));

		tools.slider.setParams($("stream-h264-bitrate-slider"), 25, 20000, 25, 5000, function(value) {
			$("stream-h264-bitrate-value").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-bitrate-slider"), 1000, (value) => __sendParam("h264_bitrate", value));

		tools.slider.setParams($("stream-h264-gop-slider"), 0, 60, 1, 30, function(value) {
			$("stream-h264-gop-value").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-gop-slider"), 1000, (value) => __sendParam("h264_gop", value));

		tools.slider.setParams($("stream-desired-fps-slider"), 0, 120, 1, 0, function(value) {
			$("stream-desired-fps-value").innerHTML = (value === 0 ? "Unlimited" : value);
		});
		tools.slider.setOnUpDelayed($("stream-desired-fps-slider"), 1000, (value) => __sendParam("desired_fps", value));

		$("stream-resolution-selector").onchange = (() => __sendParam("resolution", $("stream-resolution-selector").value));

		tools.radio.setOnClick("stream-mode-radio", __clickModeRadio, false);

		tools.slider.setParams($("stream-audio-volume-slider"), 0, 100, 1, 0, function(value) {
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

		$("stream-window").show_hook = () => __applyState(__state);
		$("stream-window").close_hook = () => __applyState(null);
	};

	/************************************************************************/

	self.getGeometry = function() {
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

	self.setJanusEnabled = function(enabled) {
		let has_webrtc = JanusStreamer.is_webrtc_available();
		let has_h264 = JanusStreamer.is_h264_available();

		let set_enabled = function(imported) {
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

	self.setState = function(state) {
		__state = state;
		if (__janus_enabled !== null) {
			__applyState(wm.isWindowVisible($("stream-window")) ? __state : null);
		}
	};

	var __applyState = function(state) {
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

	var __setActive = function() {
		$("stream-led").className = "led-green";
		$("stream-led").title = "Stream is active";
		tools.el.setEnabled($("stream-screenshot-button"), true);
		tools.el.setEnabled($("stream-reset-button"), true);
	};

	var __setInactive = function() {
		$("stream-led").className = "led-gray";
		$("stream-led").title = "Stream inactive";
		tools.el.setEnabled($("stream-screenshot-button"), false);
		tools.el.setEnabled($("stream-reset-button"), false);
	};

	var __setInfo = function(is_active, online, text) {
		$("stream-box").classList.toggle("stream-box-offline", !online);
		let el_grab = document.querySelector("#stream-window-header .window-grab");
		let el_info = $("stream-info");
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

	var __setLimitsAndValue = function(el, limits, value) {
		tools.slider.setRange(el, limits.min, limits.max);
		tools.slider.setValue(el, value);
	};

	var __resetStream = function(mode=null) {
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

	var __clickModeRadio = function() {
		let mode = tools.radio.getValue("stream-mode-radio");
		tools.storage.set("stream.mode", mode);
		if (mode !== __streamer.getMode()) {
			tools.hidden.setVisible($("stream-image"), (mode !== "janus"));
			tools.hidden.setVisible($("stream-video"), (mode === "janus"));
			__resetStream(mode);
		}
	};

	var __clickScreenshotButton = function() {
		let el = document.createElement("a");
		el.href = "/api/streamer/snapshot?allow_offline=1";
		el.target = "_blank";
		document.body.appendChild(el);
		el.click();
		setTimeout(() => document.body.removeChild(el), 0);
	};

	var __clickResetButton = function() {
		wm.confirm("Are you sure you want to reset stream?").then(function (ok) {
			if (ok) {
				__resetStream();
				let http = tools.makeRequest("POST", "/api/streamer/reset", function() {
					if (http.readyState === 4) {
						if (http.status !== 200) {
							wm.error("Can't reset stream:<br>", http.responseText);
						}
					}
				});
			}
		});
	};

	var __sendParam = function(name, value) {
		let http = tools.makeRequest("POST", `/api/streamer/set_params?${name}=${value}`, function() {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					wm.error("Can't configure stream:<br>", http.responseText);
				}
			}
		});
	};

	var __makeStringResolution = function(resolution) {
		return `${resolution.width}x${resolution.height}`;
	};

	__init__();
}

export function Streamer2() {
	var self = this;

	/************************************************************************/

	var __janus_enabled = null;
	var __streamer = null;

	var __state = null;
	var __resolution = {"width": 640, "height": 480};

	var __init__ = function() {
		__streamer = new MjpegStreamer2(__setActive, __setInactive, __setInfo);

		$("stream-led2").title = "Stream inactive";

		tools.slider.setParams($("stream-quality-slider2"), 5, 100, 5, 80, function(value) {
			$("stream-quality-value2").innerHTML = `${value}%`;
		});
		tools.slider.setOnUpDelayed($("stream-quality-slider2"), 1000, (value) => __sendParam("quality", value));

		tools.slider.setParams($("stream-h264-bitrate-slider2"), 25, 20000, 25, 5000, function(value) {
			$("stream-h264-bitrate-value2").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-bitrate-slider2"), 1000, (value) => __sendParam("h264_bitrate", value));

		tools.slider.setParams($("stream-h264-gop-slider2"), 0, 60, 1, 30, function(value) {
			$("stream-h264-gop-value2").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-gop-slider2"), 1000, (value) => __sendParam("h264_gop", value));

		tools.slider.setParams($("stream-desired-fps-slider2"), 0, 120, 1, 0, function(value) {
			$("stream-desired-fps-value2").innerHTML = (value === 0 ? "Unlimited" : value);
		});
		tools.slider.setOnUpDelayed($("stream-desired-fps-slider2"), 1000, (value) => __sendParam("desired_fps", value));

		$("stream-resolution-selector2").onchange = (() => __sendParam("resolution", $("stream-resolution-selector2").value));

		tools.radio.setOnClick("stream-mode-radio2", __clickModeRadio, false);

		tools.slider.setParams($("stream-audio-volume-slider2"), 0, 100, 1, 0, function(value) {
			$("stream-video2").muted = !value;
			$("stream-video2").volume = value / 100;
			$("stream-audio-volume-value2").innerHTML = value + "%";
			if (__streamer.getMode() === "janus") {
				let allow_audio = !$("stream-video2").muted;
				if (__streamer.isAudioAllowed() !== allow_audio) {
					__resetStream();
				}
			}
		});

		tools.el.setOnClick($("stream-screenshot-button2"), __clickScreenshotButton);
		tools.el.setOnClick($("stream-reset-button2"), __clickResetButton);

		$("stream-window2").show_hook = () => __applyState(__state);
		$("stream-window2").close_hook = () => __applyState(null);
	};

	/************************************************************************/

	self.getGeometry = function() {
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

	self.setJanusEnabled = function(enabled) {
		let has_webrtc = JanusStreamer.is_webrtc_available();
		let has_h264 = JanusStreamer.is_h264_available();

		let set_enabled = function(imported) {
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

	self.setState = function(state) {
		__state = state;
		if (__janus_enabled !== null) {
			__applyState(wm.isWindowVisible($("stream-window2")) ? __state : null);
		}
	};

	var __applyState = function(state) {
		if (state) {
			tools.feature.setEnabled($("stream-quality2"), state.features.quality && (state.streamer === null || state.streamer.encoder.quality > 0));
			tools.feature.setEnabled($("stream-h264-bitrate2"), state.features.h264 && __janus_enabled);
			tools.feature.setEnabled($("stream-h264-gop2"), state.features.h264 && __janus_enabled);
			tools.feature.setEnabled($("stream-resolution2"), state.features.resolution);

			if (state.streamer) {
				tools.el.setEnabled($("stream-quality-slider2"), true);
				tools.slider.setValue($("stream-quality-slider2"), state.streamer.encoder.quality);

				if (state.features.h264 && __janus_enabled) {
					__setLimitsAndValue($("stream-h264-bitrate-slider2"), state.limits.h264_bitrate, state.streamer.h264.bitrate);
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

			__streamer.ensureStream(state.streamer);

		} else {
			__streamer.stopStream();
		}
	};

	var __setActive = function() {
		$("stream-led2").className = "led-green";
		$("stream-led2").title = "Stream is active";
		tools.el.setEnabled($("stream-screenshot-button2"), true);
		tools.el.setEnabled($("stream-reset-button2"), true);
	};

	var __setInactive = function() {
		$("stream-led2").className = "led-gray";
		$("stream-led2").title = "Stream inactive";
		tools.el.setEnabled($("stream-screenshot-button2"), false);
		tools.el.setEnabled($("stream-reset-button2"), false);
	};

	var __setInfo = function(is_active, online, text) {
		$("stream-box2").classList.toggle("stream-box-offline", !online);
		let el_grab = document.querySelector("#stream-window-header2 .window-grab");
		let el_info = $("stream-info2");
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

	var __setLimitsAndValue = function(el, limits, value) {
		tools.slider.setRange(el, limits.min, limits.max);
		tools.slider.setValue(el, value);
	};

	var __resetStream = function(mode=null) {
		if (mode === null) {
			mode = __streamer.getMode();
		}
		__streamer.stopStream();
		if (mode === "janus") {
			__streamer = new JanusStreamer(__setActive, __setInactive, __setInfo, !$("stream-video2").muted);
		} else { // mjpeg
			__streamer = new MjpegStreamer2(__setActive, __setInactive, __setInfo);
			tools.feature.setEnabled($("stream-audio2"), false); // Enabling in stream_janus.js
		}
		if (wm.isWindowVisible($("stream-window2"))) {
			__streamer.ensureStream(__state);
		}
	};

	var __clickModeRadio = function() {
		let mode = tools.radio.getValue("stream-mode-radio2");
		tools.storage.set("stream.mode", mode);
		if (mode !== __streamer.getMode()) {
			tools.hidden.setVisible($("stream-image2"), (mode !== "janus"));
			tools.hidden.setVisible($("stream-video2"), (mode === "janus"));
			__resetStream(mode);
		}
	};

	var __clickScreenshotButton = function() {
		let el = document.createElement("a");
		el.href = "/api/streamer2/snapshot?allow_offline=1";
		el.target = "_blank";
		document.body.appendChild(el);
		el.click();
		setTimeout(() => document.body.removeChild(el), 0);
	};

	var __clickResetButton = function() {
		wm.confirm("Are you sure you want to reset stream?").then(function (ok) {
			if (ok) {
				__resetStream();
				let http = tools.makeRequest("POST", "/api/streamer2/reset", function() {
					if (http.readyState === 4) {
						if (http.status !== 200) {
							wm.error("Can't reset stream:<br>", http.responseText);
						}
					}
				});
			}
		});
	};

	var __sendParam = function(name, value) {
		let http = tools.makeRequest("POST", `/api/streamer2/set_params?${name}=${value}`, function() {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					wm.error("Can't configure stream:<br>", http.responseText);
				}
			}
		});
	};

	var __makeStringResolution = function(resolution) {
		return `${resolution.width}x${resolution.height}`;
	};

	__init__();
}

export function Streamer3() {
	var self = this;

	/************************************************************************/

	var __janus_enabled = null;
	var __streamer = null;

	var __state = null;
	var __resolution = {"width": 640, "height": 480};

	var __init__ = function() {
		__streamer = new MjpegStreamer3(__setActive, __setInactive, __setInfo);

		$("stream-led3").title = "Stream inactive";

		tools.slider.setParams($("stream-quality-slider3"), 5, 100, 5, 80, function(value) {
			$("stream-quality-value3").innerHTML = `${value}%`;
		});
		tools.slider.setOnUpDelayed($("stream-quality-slider3"), 1000, (value) => __sendParam("quality", value));

		tools.slider.setParams($("stream-h264-bitrate-slider3"), 25, 20000, 25, 5000, function(value) {
			$("stream-h264-bitrate-value3").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-bitrate-slider3"), 1000, (value) => __sendParam("h264_bitrate", value));

		tools.slider.setParams($("stream-h264-gop-slider3"), 0, 60, 1, 30, function(value) {
			$("stream-h264-gop-value3").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-gop-slider3"), 1000, (value) => __sendParam("h264_gop", value));

		tools.slider.setParams($("stream-desired-fps-slider3"), 0, 120, 1, 0, function(value) {
			$("stream-desired-fps-value3").innerHTML = (value === 0 ? "Unlimited" : value);
		});
		tools.slider.setOnUpDelayed($("stream-desired-fps-slider3"), 1000, (value) => __sendParam("desired_fps", value));

		$("stream-resolution-selector3").onchange = (() => __sendParam("resolution", $("stream-resolution-selector3").value));

		tools.radio.setOnClick("stream-mode-radio3", __clickModeRadio, false);

		tools.slider.setParams($("stream-audio-volume-slider3"), 0, 100, 1, 0, function(value) {
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

	self.getGeometry = function() {
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

	self.setJanusEnabled = function(enabled) {
		let has_webrtc = JanusStreamer.is_webrtc_available();
		let has_h264 = JanusStreamer.is_h264_available();

		let set_enabled = function(imported) {
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

	self.setState = function(state) {
		__state = state;
		if (__janus_enabled !== null) {
			__applyState(wm.isWindowVisible($("stream-window3")) ? __state : null);
		}
	};

	var __applyState = function(state) {
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

	var __setActive = function() {
		$("stream-led3").className = "led-green";
		$("stream-led3").title = "Stream is active";
		tools.el.setEnabled($("stream-screenshot-button3"), true);
		tools.el.setEnabled($("stream-reset-button3"), true);
	};

	var __setInactive = function() {
		$("stream-led3").className = "led-gray";
		$("stream-led3").title = "Stream inactive";
		tools.el.setEnabled($("stream-screenshot-button3"), false);
		tools.el.setEnabled($("stream-reset-button3"), false);
	};

	var __setInfo = function(is_active, online, text) {
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

	var __setLimitsAndValue = function(el, limits, value) {
		tools.slider.setRange(el, limits.min, limits.max);
		tools.slider.setValue(el, value);
	};

	var __resetStream = function(mode=null) {
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

	var __clickModeRadio = function() {
		let mode = tools.radio.getValue("stream-mode-radio3");
		tools.storage.set("stream.mode", mode);
		if (mode !== __streamer.getMode()) {
			tools.hidden.setVisible($("stream-image3"), (mode !== "janus"));
			tools.hidden.setVisible($("stream-video3"), (mode === "janus"));
			__resetStream(mode);
		}
	};

	var __clickScreenshotButton = function() {
		let el = document.createElement("a");
		el.href = "/api/streamer3/snapshot?allow_offline=1";
		el.target = "_blank";
		document.body.appendChild(el);
		el.click();
		setTimeout(() => document.body.removeChild(el), 0);
	};

	var __clickResetButton = function() {
		wm.confirm("Are you sure you want to reset stream?").then(function (ok) {
			if (ok) {
				__resetStream();
				let http = tools.makeRequest("POST", "/api/streamer3/reset", function() {
					if (http.readyState === 4) {
						if (http.status !== 200) {
							wm.error("Can't reset stream:<br>", http.responseText);
						}
					}
				});
			}
		});
	};

	var __sendParam = function(name, value) {
		let http = tools.makeRequest("POST", `/api/streamer3/set_params?${name}=${value}`, function() {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					wm.error("Can't configure stream:<br>", http.responseText);
				}
			}
		});
	};

	var __makeStringResolution = function(resolution) {
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
	var __resolution = {"width": 640, "height": 480};

	var __init__ = function() {
		__streamer = new MjpegStreamer4(__setActive, __setInactive, __setInfo);

		$("stream-led4").title = "Stream inactive";

		tools.slider.setParams($("stream-quality-slider4"), 5, 100, 5, 80, function(value) {
			$("stream-quality-value4").innerHTML = `${value}%`;
		});
		tools.slider.setOnUpDelayed($("stream-quality-slider4"), 1000, (value) => __sendParam("quality", value));

		tools.slider.setParams($("stream-h264-bitrate-slider4"), 25, 20000, 25, 5000, function(value) {
			$("stream-h264-bitrate-value4").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-bitrate-slider4"), 1000, (value) => __sendParam("h264_bitrate", value));

		tools.slider.setParams($("stream-h264-gop-slider4"), 0, 60, 1, 30, function(value) {
			$("stream-h264-gop-value4").innerHTML = value;
		});
		tools.slider.setOnUpDelayed($("stream-h264-gop-slider4"), 1000, (value) => __sendParam("h264_gop", value));

		tools.slider.setParams($("stream-desired-fps-slider4"), 0, 120, 1, 0, function(value) {
			$("stream-desired-fps-value4").innerHTML = (value === 0 ? "Unlimited" : value);
		});
		tools.slider.setOnUpDelayed($("stream-desired-fps-slider4"), 1000, (value) => __sendParam("desired_fps", value));

		$("stream-resolution-selector4").onchange = (() => __sendParam("resolution", $("stream-resolution-selector4").value));

		tools.radio.setOnClick("stream-mode-radio4", __clickModeRadio, false);

		tools.slider.setParams($("stream-audio-volume-slider4"), 0, 100, 1, 0, function(value) {
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
	};

	/************************************************************************/

	self.getGeometry = function() {
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

	self.setJanusEnabled = function(enabled) {
		let has_webrtc = JanusStreamer.is_webrtc_available();
		let has_h264 = JanusStreamer.is_h264_available();

		let set_enabled = function(imported) {
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

	self.setState = function(state) {
		__state = state;
		if (__janus_enabled !== null) {
			__applyState(wm.isWindowVisible($("stream-window4")) ? __state : null);
		}
	};

	var __applyState = function(state) {
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

	var __setActive = function() {
		$("stream-led4").className = "led-green";
		$("stream-led4").title = "Stream is active";
		tools.el.setEnabled($("stream-screenshot-button4"), true);
		tools.el.setEnabled($("stream-reset-button4"), true);
	};

	var __setInactive = function() {
		$("stream-led4").className = "led-gray";
		$("stream-led4").title = "Stream inactive";
		tools.el.setEnabled($("stream-screenshot-button4"), false);
		tools.el.setEnabled($("stream-reset-button4"), false);
	};

	var __setInfo = function(is_active, online, text) {
		$("stream-box4").classList.toggle("stream-box-offline", !online);
		let el_grab = document.querySelector("#stream-window-header4 .window-grab");
		let el_info = $("stream-info4");
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

	var __setLimitsAndValue = function(el, limits, value) {
		tools.slider.setRange(el, limits.min, limits.max);
		tools.slider.setValue(el, value);
	};

	var __resetStream = function(mode=null) {
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

	var __clickModeRadio = function() {
		let mode = tools.radio.getValue("stream-mode-radio4");
		tools.storage.set("stream.mode", mode);
		if (mode !== __streamer.getMode()) {
			tools.hidden.setVisible($("stream-image4"), (mode !== "janus"));
			tools.hidden.setVisible($("stream-video4"), (mode === "janus"));
			__resetStream(mode);
		}
	};

	var __clickScreenshotButton = function() {
		let el = document.createElement("a");
		el.href = "/api/streamer4/snapshot?allow_offline=1";
		el.target = "_blank";
		document.body.appendChild(el);
		el.click();
		setTimeout(() => document.body.removeChild(el), 0);
	};

	var __clickResetButton = function() {
		wm.confirm("Are you sure you want to reset stream?").then(function (ok) {
			if (ok) {
				__resetStream();
				let http = tools.makeRequest("POST", "/api/streamer4/reset", function() {
					if (http.readyState === 4) {
						if (http.status !== 200) {
							wm.error("Can't reset stream:<br>", http.responseText);
						}
					}
				});
			}
		});
	};

	var __sendParam = function(name, value) {
		let http = tools.makeRequest("POST", `/api/streamer4/set_params?${name}=${value}`, function() {
			if (http.readyState === 4) {
				if (http.status !== 200) {
					wm.error("Can't configure stream:<br>", http.responseText);
				}
			}
		});
	};

	var __makeStringResolution = function(resolution) {
		return `${resolution.width}x${resolution.height}`;
	};

	__init__();
}
