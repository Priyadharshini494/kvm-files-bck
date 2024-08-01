import subprocess

def run_i2cset_command():
    command = "i2cset -y 1 0x72 0x00 0x03"
    try:
        subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        pass

if __name__ == "__main__":
    run_i2cset_command()
