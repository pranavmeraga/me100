# hx711.py - inpsired from official MicroPython HX711 library

from machine import Pin
import time

class HX711:
    def __init__(self, dout, sck, gain=128):
        self.pd_sck = Pin(sck, Pin.OUT)
        self.dout = Pin(dout, Pin.IN)
        self.gain = 0
        self.offset = 0
        self.set_gain(gain)

    def set_gain(self, gain):
        if gain == 128:
            self.gain = 1
        elif gain == 64:
            self.gain = 3
        elif gain == 32:
            self.gain = 2
        self.pd_sck.off()
        self.read()

    def is_ready(self):
        return self.dout.value() == 0

    def read(self):
        while not self.is_ready():
            pass

        data = 0
        for _ in range(24):
            self.pd_sck.on()
            data = data << 1
            self.pd_sck.off()
            if self.dout.value():
                data += 1

        for _ in range(self.gain):
            self.pd_sck.on()
            self.pd_sck.off()

        if data & 0x800000:
            data |= ~0xffffff

        return data

    def tare(self, times=15):
        total = 0
        for _ in range(times):
            total += self.read()
            time.sleep_ms(10)
        self.offset = total / times
        return self.offset

    def get_units(self, scale=1, times=5):
        total = 0
        for _ in range(times):
            total += self.read()
            time.sleep_ms(10)
        value = (total / times) - self.offset
        return value / scale
