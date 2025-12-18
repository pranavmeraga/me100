# DishDuty Sensor Unit: Ultrasonic + Load Cell + RFID + ESP-NOW
# Simple HTTP server for viewing counts and duty order

from machine import Pin, SPI
import time, sys, uselect, socket
import network, espnow

# WiFi and ESP-NOW Setup
wlan = network.WLAN(network.STA_IF)
local_ip = wlan.ifconfig()[0]
print("Open http://%s/ to view DishDuty stats" % local_ip)

e = espnow.ESPNow()
e.active(True)

NOTIFIER_MAC = b"\xF4\x65\x0B\x34\x1A\x84"
e.add_peer(NOTIFIER_MAC)

def send_msg(text):
    try:
        e.send(NOTIFIER_MAC, text)
    except OSError as ex:
        print("ESP-NOW send error:", ex)

# People and data management
try:
    import ujson as json
except ImportError:
    import json

UID_TO_NAME = {
    "21D5B17B": "Svanik",
    "8950B711": "Svanik",
    "A169BBA3": "Paul",
    "F9ABA011": "Paul",
    "F1589C7B": "Pranav",
    "89DB6912": "Pranav",
}

ALL_NAMES = sorted(set(UID_TO_NAME.values()))
COUNTS_FILE = "dish_counts.json"
DUTY_FILE = "duty_order.json"

def load_counts():
    try:
        with open(COUNTS_FILE, "r") as f:
            data = json.load(f)
    except:
        data = {}
    for n in ALL_NAMES:
        data.setdefault(n, 0)
    return data

def save_counts(counts):
    try:
        with open(COUNTS_FILE, "w") as f:
            json.dump(counts, f)
    except Exception as e:
        print("Error saving counts:", e)

def load_duty_order():
    try:
        with open(DUTY_FILE, "r") as f:
            order = json.load(f)
    except:
        order = list(ALL_NAMES)
    seen = set()
    cleaned = []
    for n in order:
        if n in ALL_NAMES and n not in seen:
            cleaned.append(n)
            seen.add(n)
    for n in ALL_NAMES:
        if n not in seen:
            cleaned.append(n)
    return cleaned

def save_duty_order(order):
    try:
        with open(DUTY_FILE, "w") as f:
            json.dump(order, f)
    except Exception as e:
        print("Error saving duty order:", e)

name_counts = load_counts()
duty_order = load_duty_order()
last_cleaner = None
next_up_name = None

def sorted_names_by_duty():
    return sorted(
        ALL_NAMES,
        key=lambda n: (name_counts.get(n, 0), duty_order.index(n)),
    )

def recompute_next_up():
    global next_up_name
    ordered = sorted_names_by_duty()
    next_up_name = ordered[0] if ordered else "---"
    return next_up_name

recompute_next_up()

print("Initial counts:", name_counts)
print("Duty order:", duty_order)
print("Next up:", next_up_name)

send_msg(("N|" + next_up_name).encode("utf-8"))

# HTTP Server
def render_html(counts, next_up, last_cleaner):
    total = sum(counts.values())
    ordered_names = sorted_names_by_duty()
    rows = ""
    for name in ordered_names:
        cnt = counts.get(name, 0)
        rows += f"<tr><td>{name}</td><td>{cnt}</td></tr>"
    last_text = last_cleaner if last_cleaner else "---"
    next_text = next_up if next_up else "---"
    return f"""HTTP/1.1 200 OK
Content-Type: text/html

<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>DishDuty Sensor</title>
  <style>
    body {{font-family:system-ui;background:#020617;color:#e5e7eb;display:flex;justify-content:center;padding:24px}}
    .card {{background:#020617;border-radius:16px;border:1px solid #1f2937;padding:20px 24px;max-width:460px;width:100%}}
    h1 {{margin-top:0;font-size:20px}}
    table {{width:100%;border-collapse:collapse;margin-top:8px;margin-bottom:12px}}
    th,td {{text-align:left;padding:4px 0;border-bottom:1px solid #111827}}
    th {{color:#9ca3af;font-weight:500}}
    .total {{font-size:13px;color:#9ca3af;margin-top:4px}}
    .meta {{font-size:13px;color:#9ca3af;margin-top:8px}}
  </style>
</head>
<body>
  <div class="card">
    <h1>DishDuty · Sensor Node</h1>
    <p class="meta">Tracks completed dish cycles with soap usage verification.</p>
    <table>
      <tr><th>Name</th><th>Dishes done</th></tr>
      {rows}
    </table>
    <div class="total">Total: <strong>{total}</strong></div>
    <div class="meta">Next up: <strong>{next_text}</strong><br/>Last: <strong>{last_text}</strong></div>
  </div>
</body>
</html>"""

def start_http_server():
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(2)
    s.setblocking(False)
    print("HTTP server: http://%s/" % local_ip)
    return s

http_sock = start_http_server()

def handle_http_client():
    try:
        cl, addr = http_sock.accept()
    except OSError:
        return
    try:
        req = cl.recv(1024).decode("utf-8")
        if not req:
            cl.close()
            return
        resp = render_html(name_counts, next_up_name, last_cleaner)
        cl.sendall(resp.encode("utf-8"))
    except Exception as ex:
        print("HTTP error:", ex)
    finally:
        cl.close()

# Ultrasonic Sensors
TRIG1, ECHO1 = 32, 33
TRIG2, ECHO2 = 27, 14

trig1 = Pin(TRIG1, Pin.OUT)
echo1 = Pin(ECHO1, Pin.IN)
trig2 = Pin(TRIG2, Pin.OUT)
echo2 = Pin(ECHO2, Pin.IN)
trig1.off()
trig2.off()
time.sleep_ms(200)

US_MIN = 1.0
US_MAX = 7.0

def distance_cm(trig, echo):
    trig.off()
    time.sleep_us(2)
    trig.on()
    time.sleep_us(10)
    trig.off()
    t0 = time.ticks_us()
    while echo.value() == 0:
        if time.ticks_diff(time.ticks_us(), t0) > 30000:
            return None
    start = time.ticks_us()
    while echo.value() == 1:
        if time.ticks_diff(time.ticks_us(), start) > 30000:
            return None
    end = time.ticks_us()
    duration = time.ticks_diff(end, start)
    return (duration * 0.0343) / 2.0

INTERVAL_MS = 500
OFFSET_MS = 250

now = time.ticks_ms()
next_us1 = now
next_us2 = time.ticks_add(now, OFFSET_MS)
last_status = "GREEN"

# Load Cell (HX711)
from hx711 import HX711

DT, SCK = 12, 13
hx = HX711(dout=DT, sck=SCK)
CAL = 1143.3771

print("Taring load cell...")
time.sleep(2)
hx.tare()
print("Load cell ready.\n")

soap_baseline = None
soap_state = "no_bottle"
last_soap_weight = 0.0

SOAP_PRESENT_THRESHOLD = 100
SOAP_USE_THRESHOLD = 3
SOAP_EMPTY_THRESHOLD = 75
SOAP_NEW_BOTTLE_DELTA = 300

def read_weight():
    w = hx.get_units(scale=CAL, times=6)
    if abs(w) < 0.5:
        w = 0.0
    return w

def process_soap_weight(w, should_track=True):
    global soap_baseline, soap_state, last_soap_weight
    
    if w < SOAP_PRESENT_THRESHOLD:
        if soap_state != "removed":
            if should_track:
                print("Soap bottle lifted/removed.")
            soap_state = "removed"
        last_soap_weight = w
        return False
    
    if soap_state == "removed" and w >= SOAP_PRESENT_THRESHOLD:
        if should_track:
            print("Soap bottle placed back. Weight: %.1f g" % w)
        
        if soap_baseline is None:
            soap_baseline = w
            if should_track:
                print("   Baseline set: %.1f g" % soap_baseline)
        else:
            delta = w - soap_baseline
            if delta < -SOAP_USE_THRESHOLD:
                if should_track:
                    soap_used = abs(delta)
                    print("   Soap used: %.1f grams" % soap_used)
                    soap_baseline = w
                    if soap_baseline < SOAP_EMPTY_THRESHOLD:
                        print("   Bottle nearly empty: %.1f g" % soap_baseline)
                else:
                    print("   Soap movement before scan - not counted")
                    soap_baseline = w
                soap_state = "present"
                last_soap_weight = w
                return should_track
            elif abs(delta) > SOAP_NEW_BOTTLE_DELTA:
                if should_track:
                    print("   New bottle detected! Weight: %.1f g" % w)
                soap_baseline = w
                soap_state = "present"
                last_soap_weight = w
                return False
            else:
                if should_track:
                    print("   No soap use detected (delta: %.1f g)" % delta)
        soap_state = "present"
        last_soap_weight = w
        return False
    
    if soap_state == "present":
        if soap_baseline and soap_baseline < SOAP_EMPTY_THRESHOLD:
            if should_track and time.ticks_ms() % 30000 < 500:
                print("   Bottle nearly empty: %.1f g" % soap_baseline)
        last_soap_weight = w
    return False

# Alert State Machine
alert_active = False
alert_start_time = 0
last_scan_time = 0
grace_period_ms = 15000
scan_grace_ms = 30000
scan_timeout_ms = 60000
last_rfid_scan = None
soap_used_during_alert = False
beep_mode = None

# RFID Scanner
from mfrc22 import MFRC522

SCK_RFID, MOSI, MISO = 5, 19, 21
CS_RFID, RST_RFID = 26, 25

poll = uselect.poll()
poll.register(sys.stdin, uselect.POLLIN)

def check_for_reset_from_serial():
    global name_counts
    res = poll.poll(0)
    if res:
        ch = sys.stdin.read(1)
        if ch in ("r", "R"):
            for k in name_counts:
                name_counts[k] = 0
            save_counts(name_counts)
            print("\n*** COUNTS RESET ***")
            recompute_next_up()

rst_pin = Pin(RST_RFID, Pin.OUT)
rst_pin.value(1)

spi = SPI(2, baudrate=2500000, polarity=0, phase=0,
          sck=Pin(SCK_RFID), mosi=Pin(MOSI), miso=Pin(MISO))
rfid = MFRC522(spi=spi, cs=Pin(CS_RFID, Pin.OUT))

print("RFID ready.\n")

# Clean Event Registration
def register_clean(name):
    global alert_active, last_cleaner, duty_order
    global soap_used_during_alert, last_rfid_scan, beep_mode
    global last_scan_time
    
    print("DISH CLEAN CONFIRMED by", name)
    
    name_counts[name] = name_counts.get(name, 0) + 1
    save_counts(name_counts)
    
    if name in duty_order:
        duty_order.remove(name)
    duty_order.append(name)
    save_duty_order(duty_order)
    
    last_cleaner = name
    recompute_next_up()
    
    print("Updated counts:", name_counts)
    print("New duty order:", duty_order)
    print("Next up:", next_up_name)
    
    alert_active = False
    soap_used_during_alert = False
    last_rfid_scan = None
    beep_mode = None
    last_scan_time = 0
    
    send_msg(("R|" + name).encode("utf-8"))
    send_msg(("N|" + next_up_name).encode("utf-8"))
    send_msg(b"S|GREEN")
    send_msg(b"B|OFF")

# Main Loop
print("Starting main loop...")
print("US thresholds: %.1f - %.1f cm" % (US_MIN, US_MAX))

while True:
    now = time.ticks_ms()
    
    handle_http_client()
    
    # RFID
    check_for_reset_from_serial()
    stat, _ = rfid.request(rfid.REQIDL)
    if stat == rfid.OK:
        stat, uid = rfid.anticoll()
        if stat == rfid.OK:
            uid_str = "".join("{:02X}".format(b) for b in uid[:4])
            print("\n" + "="*40)
            print("RFID DETECTED!")
            print("   UID:", uid_str)
            
            if uid_str in UID_TO_NAME:
                name = UID_TO_NAME[uid_str]
                print("   Name:", name)
                print("   Alert active:", alert_active)
                
                if alert_active:
                    last_rfid_scan = name
                    last_scan_time = now
                    print("   Scan recorded during alert.")
                    print("   Soap used:", soap_used_during_alert)
                    if beep_mode is not None:
                        beep_mode = None
                        send_msg(b"B|OFF")
                        print("   Buzzer stopped by scan")
                else:
                    print("   Scan outside alert")
            else:
                print("   Unknown UID!")
            print("="*40 + "\n")
            
            rfid.select_tag(uid)
            rfid.stop_crypto1()
            time.sleep(1)
    
    # Load Cell
    weight = read_weight()
    if now % 5000 < 100:
        print("Weight: %.1f g | Baseline: %s | State: %s" % 
              (weight, soap_baseline if soap_baseline else "None", soap_state))
    
    should_track_soap = alert_active and last_rfid_scan is not None
    soap_was_used = process_soap_weight(weight, should_track_soap)
    
    if soap_was_used:
        soap_used_during_alert = True
        print("   Soap usage logged during alert!")
    
    # Ultrasonics
    near1, near2 = False, False
    
    if time.ticks_diff(now, next_us1) >= 0:
        d1 = distance_cm(trig1, echo1)
        next_us1 = time.ticks_add(now, INTERVAL_MS)
        if d1 is not None and US_MIN < d1 < US_MAX:
            near1 = True
    
    if time.ticks_diff(now, next_us2) >= 0:
        d2 = distance_cm(trig2, echo2)
        next_us2 = time.ticks_add(now, INTERVAL_MS)
        if d2 is not None and US_MIN < d2 < US_MAX:
            near2 = True
    
    # Buzzer and LED State Machine
    both_blocked = near1 and near2
    new_status = last_status
    
    if alert_active:
        # Determine LED status
        if beep_mode == "CONSTANT":
            new_status = "RED"
        elif beep_mode == "GRACE":
            if near1 and near2:
                new_status = "RED"
            elif near1 or near2:
                new_status = "YELLOW"
            else:
                new_status = "GREEN"
        else:
            if near1 and near2:
                new_status = "RED"
            elif near1 or near2:
                new_status = "YELLOW"
            else:
                new_status = "GREEN"
        
        # Check if fully resolved
        if new_status == "GREEN" and last_rfid_scan and soap_used_during_alert:
            register_clean(last_rfid_scan)
        else:
            # Buzzer logic
            if last_scan_time > 0:
                since_scan = time.ticks_diff(now, last_scan_time)
                
                if since_scan < scan_grace_ms:
                    if beep_mode is not None:
                        beep_mode = None
                        send_msg(b"B|OFF")
                
                elif since_scan < scan_timeout_ms:
                    if both_blocked:
                        if beep_mode != "CONSTANT":
                            beep_mode = "CONSTANT"
                            send_msg(b"B|CONSTANT")
                            print("RED after 30s grace - CONSTANT buzzing")
                
                else:
                    if new_status != "GREEN":
                        if beep_mode != "CONSTANT":
                            beep_mode = "CONSTANT"
                            send_msg(b"B|CONSTANT")
                            print("1 min passed - not green, CONSTANT buzzing")
            
            else:
                since_alert = time.ticks_diff(now, alert_start_time)
                
                if beep_mode == "CONSTANT":
                    pass
                
                elif since_alert < grace_period_ms:
                    if both_blocked:
                        if beep_mode != "GRACE":
                            beep_mode = "GRACE"
                            send_msg(b"B|GRACE")
                            print("Grace period: 15s intermittent beeping")
                    else:
                        beep_mode = None
                        send_msg(b"B|OFF")
                        alert_start_time = now
                        print("Dishes moved during grace - TIMER RESET")
                
                else:
                    if beep_mode != "CONSTANT":
                        beep_mode = "CONSTANT"
                        send_msg(b"B|CONSTANT")
                        print("Grace expired - CONSTANT buzzing")
    
    else:
        # Not in alert - check for trigger
        if near1 and near2:
            alert_active = True
            alert_start_time = now
            last_rfid_scan = None
            soap_used_during_alert = False
            beep_mode = "GRACE"
            last_scan_time = 0
            new_status = "RED"
            print("\nRED ALERT! Both sensors detecting.")
            print("   15s grace beeping started.")
            send_msg(b"B|GRACE")
        elif near1 or near2:
            new_status = "YELLOW"
        else:
            new_status = "GREEN"
    
    # Send Status if Changed
    if new_status != last_status:
        last_status = new_status
        print("Status:", new_status)
        send_msg(("S|" + new_status).encode("utf-8"))
    
    time.sleep_ms(50)