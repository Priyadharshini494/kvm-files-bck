#!/bin/bash
# Disable ncm.usb0
sudo sh -c 'echo "" > /sys/kernel/config/usb_gadget/kvmd/UDC'
sudo rm /sys/kernel/config/usb_gadget/kvmd/configs/c.1/ncm.usb0

# Enable acm.usb0
sudo ln -s /sys/kernel/config/usb_gadget/kvmd/functions/acm.usb0 /sys/kernel/config/usb_gadget/kvmd/configs/c.1
sudo sh -c 'echo fe980000.usb > /sys/kernel/config/usb_gadget/kvmd/UDC'

