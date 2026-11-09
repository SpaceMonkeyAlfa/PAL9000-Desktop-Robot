import sys
import select
import machine
import uasyncio as asyncio

# Some servo code coppied from https://github.com/redoxcode/micropython-servo
class Servo:
    def __init__(self, pin_id, min_us=544.0, max_us=2400.0, min_deg=0.0, max_deg=180.0, freq=50):
        self.pwm = machine.PWM(machine.Pin(pin_id))
        self.pwm.freq(freq)
        self.current_us = 0.0
        self._slope = (min_us - max_us) / (min_deg - max_deg)
        self._offset = min_us
        self.last_write: int = 0
        self.update: int = 0
        self.smooth_factor = 5
                
    def write(self, deg):
        us = deg * self._slope + self._offset
        self.pwm.duty_ns(int(us * 1000.0)) 

    def off(self):
        self.pwm.duty_ns(0)

    async def write_loop(self):
        while True:
            update_snapshot = self.update << (8 - self.smooth_factor) #Equivelant to bitshift left by 8 (x256) then right by smooth_factor (/(2^smooth))
            #print(update_snapshot)
            self.last_write = (update_snapshot + (self.last_write) - (self.last_write >> self.smooth_factor))
            self.write(int(self.last_write)>>8)
            #print(f"{self}: writing {self.last_write>>8} ")
            await asyncio.sleep_ms(10)

lr_servo = Servo(pin_id=0)
lr_servo.update = 0
ud_servo = Servo(pin_id=1)


async def serial_input_loop():
    # Setup polling for standard input (serial/REPL)
    poller = select.poll()
    poller.register(sys.stdin, select.POLLIN)
    
    buffer = ""
    print("\n--- Serial Control Ready ---")
    print("Enter angles in format: <lr_angle> <ud_angle>")
    
    while True:
        # check serial buffer for characters
        #lr_servo.update = 180
        if poller.poll(0):
            char = sys.stdin.read(1)
            
            # If Enter is Pressed
            if char in ('\n', '\r'):
                if buffer.strip():
                    process_command(buffer.strip())
                    buffer = ""
            else:
                buffer += char
        
        await asyncio.sleep_ms(20)

def process_command(command):
    try:
        parts = command.replace(',', ' ').split()
        
        if len(parts) == 2:
            lr_angle = int(parts[0])
            ud_angle = int(parts[1])
            
            if 0 <= lr_angle <= 180:
                print(f"Updating LR servo to: {(lr_angle)}")
                lr_servo.update = (lr_angle)
            else:
                print("LR angle out of servo range (0-180)")
            
            if 0 <= ud_angle <= 20:
                print(f"Moving UD servo to: {ud_angle}")
                ud_servo.update = ud_angle
            else:
                print("UD angle out of servo range (0-45)")
        else:
            print("format error.")
            
    except ValueError:
        print("Invalid input. Please enter numbers.")

async def main():
    print("Starting servo tasks...")
    asyncio.create_task(lr_servo.write_loop())
    asyncio.create_task(ud_servo.write_loop())
    print("Servo tasks created")

    await serial_input_loop()

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\nStopped by user.")
except Exception as e:
    print(f"Fatal error: {type(e).__name__}: {e}")
finally:
    lr_servo.off()
    ud_servo.off()
