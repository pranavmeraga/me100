from machine import Pin
import time

buzzer = Pin(33, Pin.OUT)

while True:
    buzzer.on()
    time.sleep(0.5)
    buzzer.off()
    time.sleep(0.5)
