#!/bin/bash

# Disable acm.usb0
sudo sh -c 'echo "" > /sys/kernel/config/usb_gadget/kvmd/UDC'
if [ -e /sys/kernel/config/usb_gadget/kvmd/configs/c.1/acm.usb0 ]; then
    sudo rm /sys/kernel/config/usb_gadget/kvmd/configs/c.1/acm.usb0
fi

# Enable ncm.usb0
if [ ! -d /sys/kernel/config/usb_gadget/kvmd/functions/ncm.usb0 ]; then
    sudo mkdir /sys/kernel/config/usb_gadget/kvmd/functions/ncm.usb0
fi
if [ ! -e /sys/kernel/config/usb_gadget/kvmd/configs/c.1/ncm.usb0 ]; then
    sudo ln -s /sys/kernel/config/usb_gadget/kvmd/functions/ncm.usb0 /sys/kernel/config/usb_gadget/kvmd/configs/c.1
fi
sudo sh -c 'echo fe980000.usb > /sys/kernel/config/usb_gadget/kvmd/UDC'

