#!/bin/bash

# Serial device to set (replace with your desired device)
SERIAL_DEVICE="/dev/ttyAMA0"

# Minicom configuration file
MINICOM_CONFIG="/etc/minicom/minirc.dfl"

# Backup the existing Minicom configuration file (optional)
sudo cp "$MINICOM_CONFIG" "$MINICOM_CONFIG.bak"

# Edit the Minicom configuration file to update the serial device setting
sudo sed -i "s|^pu port[[:space:]]*[/a-zA-Z0-9]*$|pu port             $SERIAL_DEVICE|" "$MINICOM_CONFIG"

echo "Minicom serial device updated to: $SERIAL_DEVICE"
