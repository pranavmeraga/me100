# DishDuty Notifier Unit: OLED + LEDs + Buzzer + ESP-NOW (Receiver)
from machine import Pin, I2C
import time
import network, espnow
from oled import SSD1306_I2C

# ESP-NOW Setup
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

e = espnow.ESPNow()
e.active(True)

SENSOR_MAC = b"\xF4\x65\x0B\x30\x1a\x84"
e.add_peer(SENSOR_MAC)

# OLED Setup
I2C_SCL = 32
I2C_SDA = 15
OLED_ADDR = 0x3D

i2c = I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA))
print("I2C scan:", i2c.scan())

oled = SSD1306_I2C(128, 64, i2c, addr=OLED_ADDR)

# LED and Buzzer Setup
green = Pin(14, Pin.OUT)
red = Pin(26, Pin.OUT)
yellow = Pin(27, Pin.OUT)
buzzer = Pin(33, Pin.OUT)

def led_green():
    red.off()
    yellow.off()
    green.on()

def led_yellow():
    red.off()
    green.off()
    yellow.on()

def led_red():
    green.off()
    yellow.off()
    red.on()

# Buzzer Control
beep_mode = "OFF"
beep_state = False
last_beep_toggle = 0
BEEP_GRACE_INTERVAL = 500

def update_buzzer():
    """Update buzzer based on current beep mode"""
    global beep_state, last_beep_toggle
    
    now = time.ticks_ms()
    
    if beep_mode == "OFF":
        buzzer.off()
        beep_state = False
    
    elif beep_mode == "GRACE":
        if time.ticks_diff(now, last_beep_toggle) >= BEEP_GRACE_INTERVAL:
            beep_state = not beep_state
            if beep_state:
                buzzer.on()
            else:
                buzzer.off()
            last_beep_toggle = now

# State Variables
current_status = "GREEN"
last_cleaner = "---"
next_up = "---"

def update_display():
    oled.fill(0)
    oled.text("DishDuty", 0, 0)
    
    status_display = ""
    if current_status == "GREEN":
        status_display = "Status: OK"
    elif current_status == "YELLOW":
        status_display = "Status: DISHES"
    elif current_status == "RED":
        status_display = "Status: ALERT!"
    
    oled.text(status_display, 0, 12)
    oled.text("----------------", 0, 24)
    
    oled.text("Next Up:", 0, 32)
    name = next_up if next_up else "---"
    x_pos = max(0, (128 - len(name) * 8) // 2)
    oled.text(name, x_pos, 44)
    
    oled.text("Last: " + last_cleaner[:10], 0, 56)
    
    oled.show()

def apply_status():
    """Update LEDs based on status"""
    if current_status == "GREEN":
        led_green()
    elif current_status == "YELLOW":
        led_yellow()
    elif current_status == "RED":
        led_red()
    else:
        led_green()

apply_status()
update_display()

# Main Loop
print("Notifier ready. Waiting for messages...\n")

while True:
    host, msg = e.recv(20)
    
    if msg:
        try:
            text = msg.decode("utf-8")
        except:
            print("Non-text msg:", msg)
            continue
        
        parts = text.split("|", 1)
        if len(parts) != 2:
            print("Malformed msg:", text)
            continue
        
        mtype, payload = parts[0], parts[1]
        
        if mtype == "S":
            current_status = payload
            print("Status:", current_status)
            apply_status()
            update_display()
        
        elif mtype == "R":
            last_cleaner = payload
            print("Last cleaner:", last_cleaner)
            update_display()
        
        elif mtype == "N":
            next_up = payload
            print("Next up:", next_up)
            update_display()
        
        elif mtype == "B":
            beep_mode = payload
            print("Beep mode:", beep_mode)
            if beep_mode == "OFF":
                buzzer.off()
        
        else:
            print("Unknown msg type:", mtype)
    
    update_buzzer()
    time.sleep_ms(50)
