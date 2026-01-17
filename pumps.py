from gpiozero import OutputDevice
import time

# pump pin mapping (just cahange the shit)
PUMP_PINS = {
    1: 17,
    2: 18,
    3: 27,
    4: 22,
    5: 23,
    6: 24,
    7: 25,
    8: 5,
}

# pump object init 
pumps = {
    i: OutputDevice(pin, active_high=True, initial_value=False)
    for i, pin in PUMP_PINS.items()
}


# recipe list
RECIPES = {
    "HAPPY": {
        "name": "rnadom shit",
        "steps": [(1, 2.0), (3, 1.0), (5, 0.5)]
    }
}
# ^^ 
# (which pump, seconds)

def stop_all_pumps():
    for p in pumps.values():
        p.off()


# run a recipe, with status to put on screen
def run_recipe(steps, status_cb=None):
    try:
        stop_all_pumps()

        for pump_num, secs in steps:
            if status_cb:
                status_cb(f"Dispensing: Pump {pump_num} for {secs:.1f}s")

            pumps[pump_num].on()
            time.sleep(secs)
            pumps[pump_num].off()

        if status_cb:
            status_cb("drink ready!")

    finally:
        stop_all_pumps()
