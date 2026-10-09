import sys
import select
import machine
import uasyncio as asyncio


class Servo:
    def __init__(self, pin_id, min_us=544.0, max_us=2400.0, min_deg=0.0, max_deg=180.0, freq=50):
        self.pwm = machine.PWM(machine.Pin(pin_id))
        self.pwm.freq(freq)
        self.current_us = 0.0
        self._slope = (min_us - max_us) / (min_deg - max_deg)
        self._offset = min_us
        self.last_write = 0
        self.update = 0
                
    def write(self, deg):
        us = deg * self._slope + self._offset
        self.pwm.duty_ns(int(us * 1000.0)) 

    def off(self):
        self.pwm.duty_ns(0)

    async def write_loop(self):
        while True:
            update_snapshot = self.update
            self.last_write = max(min(0.3 * update_snapshot + 0.7 * self.last_write, 360), 0)
            #self.write(self.last_write)
            print(f"{self}: writing {self.last_write} ")
            await asyncio.sleep_ms(10)

lr_servo = Servo(pin_id=0)
lr_servo.update = 50
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
                print(f"Updating LR servo to: {(lr_angle)*1.1+50}")
                lr_servo.write((lr_angle)*1.1+50)
            else:
                print("LR angle out of servo range (0-180)")
            
            if 0 <= ud_angle <= 20:
                print(f"Moving UD servo to: {ud_angle}")
                ud_servo.write(ud_angle)
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
    print("\nStopped by user. Cleaning up...")
except Exception as e:
    print(f"Fatal error: {type(e).__name__}: {e}")
finally:
    lr_servo.off()
    ud_servo.off()
