import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
GPIO.setwarnings(False) # Ignore warning for now
GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
# on_off_pin = 10
start_stop_pin = 24

GPIO.setup(start_stop_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Start/Stop button TODO: check pin

def check_buttons():
    start_switch = GPIO.input(start_stop_pin)
    # power_switch = GPIO.input(on_off_pin)
    # if not power_switch:
    #     self.rp_state = RPStates.STOPPING
    if start_switch:
        print("start")
    else:
        print("stop")

while True:
    check_buttons()
    GPIO.wait_for_edge(start_stop_pin, GPIO.FALLING)
