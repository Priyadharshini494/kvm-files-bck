import subprocess
import time
 
def run_i2cset_command():
    command = "i2cset -y 1 0x72 1"
    try:
        subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
 
if __name__ == "__main__":
    while True:
        run_i2cset_command()
        time.sleep(1)  # Optional: Add a delay to prevent excessive CPU usage
