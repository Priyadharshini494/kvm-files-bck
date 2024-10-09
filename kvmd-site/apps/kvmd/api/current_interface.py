from aiohttp import web
import os

# Function to determine the current USB interface
def get_current_interface():
    config_path = "/sys/kernel/config/usb_gadget/kvmd/configs/c.1"
    
    # Check if ACM is linked in the current configuration
    acm_link = os.path.join(config_path, "acm.usb0")
    
    # Check if NCM is linked in the current configuration
    ncm_link = os.path.join(config_path, "ncm.usb0")
    
    if os.path.islink(acm_link):
        return "ACM (Serial)"
    elif os.path.islink(ncm_link):
        return "NCM (Ethernet)"
    else:
        return "Unknown interface"

# Define the API route to fetch the current interface
async def get_interface(request):
    current_interface = get_current_interface()
    return web.json_response({"current_interface": current_interface})

# Create an aiohttp application
app = web.Application()
app.router.add_get('/current-interface', get_interface)

# Start the aiohttp server
if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=8044)

