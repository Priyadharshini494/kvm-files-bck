#!/bin/bash
 
# Desired IP address and netmask for usb0
DESIRED_IP="190.20.20.2"
DESIRED_NETMASK="255.255.255.0"
 
# Infinite loop to keep checking for the usb0 interface
while true; do
   # Check if usb0 interface exists
   if ip a | grep -q "usb0"; then
       # Check the current IP address of usb0
      CURRENT_IP=$(ip -4 addr show usb0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
 
       # If usb0 has no IP or the IP is different from the desired IP, set the IP
       if [ "$CURRENT_IP" != "$DESIRED_IP" ]; then
           sudo ifconfig usb0 $DESIRED_IP netmask $DESIRED_NETMASK
           echo "Assigned IP $DESIRED_IP to usb0 with netmask $DESIRED_NETMASK"
       else
           echo "usb0 already has the desired IP $DESIRED_IP, skipping assignment."
       fi
 
       # Exit the loop once the IP is correctly set or found
       break
   else
       echo "usb0 not found, checking again in 5 seconds..."
       # Wait for 5 seconds before checking again
       sleep 5
   fi
done
