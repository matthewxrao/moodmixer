import serial
import serial.tools.list_ports
import time

ARDUINO_PORT = "COM5"
ARDUINO_BAUDRATE = 115200

def connect_to_arduino():
    print("Available ports:")
    for p in serial.tools.list_ports.comports():
        print(f"  {p.device} | {p.description}")

    try:
        ser = serial.Serial(ARDUINO_PORT, ARDUINO_BAUDRATE, timeout=1)
        time.sleep(2)   # wait for Arduino reset
        print(f"\nConnected to Arduino on {ARDUINO_PORT}")
        return ser
    except Exception as e:
        raise Exception(f"Could not open {ARDUINO_PORT}: {e}")

def send_and_read(ser, msg):
    ser.write((msg + "\n").encode("utf-8"))
    ser.flush()

    # wait for response
    time.sleep(0.2)
    if ser.in_waiting:
        reply = ser.readline().decode("utf-8").strip()
        print(f"<< {reply}")

if __name__ == "__main__":
    try:
        arduino = connect_to_arduino()

        print("\nType commands: hi, LED ON, LED OFF, or EXIT")

        while True:
            cmd = input(">> ").strip()

            if cmd.upper() == "EXIT":
                break

            send_and_read(arduino, cmd)

        arduino.close()
        print("Closed serial.")

    except Exception as e:
        print(f"ERROR: {e}")
