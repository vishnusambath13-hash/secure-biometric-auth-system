import airsim
import time
import os

# -------------------------
# Connect to AirSim
# -------------------------

client = airsim.MultirotorClient()
client.confirmConnection()

client.enableApiControl(True)
client.armDisarm(True)

flying = False

print("[AirSim] Ready — waiting for UI commands...")

# -------------------------
# Command execution
# -------------------------

def execute(command):
    global flying

    if command == "takeoff" and not flying:
        print("[CMD] TAKEOFF")
        client.takeoffAsync().join()
        flying = True

    elif command == "forward" and flying:
        print("[CMD] START RECON")
        client.moveByVelocityAsync(3, 0, 0, 5)

    elif command == "return":
        print("[CMD] RETURN BASE")
        client.goHomeAsync().join()
        client.landAsync().join()
        flying = False

    elif command == "hover" and flying:
        print("[CMD] ABORT → HOVER")
        client.hoverAsync()

    elif command == "status":
        state = client.getMultirotorState()
        pos = state.kinematics_estimated.position
        vel = state.kinematics_estimated.linear_velocity

        print("[STATUS]")
        print("Position:", pos)
        print("Velocity:", vel)

    else:
        print("[IGNORED]", command)


# -------------------------
# File listener
# -------------------------

COMMAND_FILE = "D:/UAV_STACK/commands.txt"
LAST_COMMAND = None

while True:
    try:
        if os.path.exists(COMMAND_FILE):

            with open(COMMAND_FILE, "r") as f:
                cmd = f.read().strip()

            if cmd and cmd != LAST_COMMAND:
                print("[AirSim] Received:", cmd)
                execute(cmd)
                LAST_COMMAND = cmd

    except Exception as e:
        print("[ERROR]", e)

    time.sleep(0.3)