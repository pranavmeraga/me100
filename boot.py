import esp
import network
import time
import ntptime
import machine

print('running boot')

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

password = '1YM-)0xR'

if wlan.isconnected():
    print('connected')
    wlan.disconnect()
    time.sleep(1)
    print('disconnected')
    
if not wlan.isconnected():
    print('connecting to network...')
    wlan.connect('Berkeley-IoT', password)
    time.sleep(2)

    tries = 0
    while not wlan.isconnected() and tries < 30:
        print('...')
        wlan.connect('Berkeley-IoT', password)

        time.sleep(2)
        tries = tries + 1
    print('network config:', wlan.ifconfig())
    
    
    if wlan.isconnected():
        print("WiFi connected at", wlan.ifconfig()[0])
    else:
        print("Mission failed")
 
        

