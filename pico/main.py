import network
import time
from microdot import Microdot
from servo import Servo 

# PUT YOUR WIFI LOGIN DETAILS HERE
WIFI_SSID = ""
WIFI_PASS = ""


my_servo = Servo(pin_id=0)


wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(WIFI_SSID, WIFI_PASS)

print("Connecting to WiFi...")
while not wlan.isconnected():
    time.sleep(1)
print(f"Connected! IP Address: {wlan.ifconfig()[0]}")


app = Microdot()

@app.route('/')
def index(request):
    return "hi"
            
@app.route('/set')
def set_angle(request):
    args = request.args
    angle = args.get('angle', None)
    if angle:
        angle = int(angle)
        if 0 <= angle <= 180:
            print(f"Moving servo to: {angle}")
            my_servo.write(angle)
            return "Moved!"
        else:
            return "Angle out of servo range"
    else:
        return "No angle value specified"
try:
    print("running server..")
    app.run(host='0.0.0.0', port=8080, debug=True)
except KeyboardInterrupt:
    print("Server stopped by user. Cleaning up...")
