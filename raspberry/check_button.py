import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
GPIO.setwarnings(True) # Ignore warning for now
GPIO.setmode(GPIO.BCM) # Use physical pin numbering
# on_off_pin = 10
start_stop_pin = 24
resistor_pin = 23
GPIO.setup(resistor_pin, GPIO.OUT)
GPIO.output(resistor_pin, GPIO.HIGH)
GPIO.setup(start_stop_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Start/Stop button TODO: check pin
import time

prev_time = 0
def check_buttons():
    global prev_time
    stop_switch = GPIO.input(start_stop_pin)
    if time.time() - prev_time > 1:
        prev_time = time.time()    
        if stop_switch:
            print("stop")
        else:
            print("start")

while True:
    check_buttons()
    # GPIO.wait_for_edge(start_stop_pin, GPIO.FALLING)
