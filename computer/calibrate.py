import cv2
import serial
import threading
from pupil_apriltags import Detector


CAMERA_INDEX = 0  
SERIAL_PORT = "/dev/cu.usbmodem1101" # <-- UPDATE THIS with the Pico serial port
BAUD_RATE = 115200


GRID_ROWS = 3
GRID_COLS = 5


lr_angle = 90 
ud_angle = 22  


active_cell = 0
recorded_data = [] 


last_corners = None
last_center = None
last_id = None
last_family = None
frames_since_seen = 999
COASTING_FRAMES = 30  

# --- Serial Setup ---
try:
    pico_serial = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    print(f"Successfully connected to Pico on {SERIAL_PORT}")
except Exception as e:
    print(f"WARNING: Could not open serial port {SERIAL_PORT}. Error: {e}")
    print("Running in display-only mode.")
    pico_serial = None

detector = Detector(
    families="tag36h11",
    nthreads=4,
    quad_decimate=1.0,
    quad_sigma=0.0,
    refine_edges=1,
)

camera = cv2.VideoCapture(
    CAMERA_INDEX,
    cv2.CAP_AVFOUNDATION,
)

if not camera.isOpened():
    raise RuntimeError(
        f"Could not open camera index {CAMERA_INDEX}. "
        "Check the FFmpeg device list and macOS camera permissions."
    )

camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)


def send_serial_command(lr, ud):
    if pico_serial and pico_serial.is_open:
        try:
            command = f"{lr} {ud}\n"
            pico_serial.write(command.encode('utf-8'))
        except Exception:
            pass 

print("Starting AprilTag Tracker...")
print("Controls: Arrow Keys (or WASD) to adjust angles.q' to quit.")

while True:
    ok, frame = camera.read()

    if not ok:
        print("Failed to read from camera")
        break

    H, W = frame.shape[:2]

    # 1. DETECT FIRST
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    detections = detector.detect(gray)

    # 2. FLIP THE FRAME
    frame = cv2.flip(frame, 1)

    # Grid Cell Dimensions
    cell_h = H // GRID_ROWS
    cell_w = W // GRID_COLS

    # Calculate active cell boundaries (Target Cell)
    active_row = active_cell // GRID_COLS
    active_col = active_cell % GRID_COLS
    x1, y1 = active_col * cell_w, active_row * cell_h
    x2, y2 = x1 + cell_w, y1 + cell_h

    tag_in_active_cell = False

    # --- Detection & Memory Logic ---
    if detections:
        det = detections[0]
        
        # 3. MATHEMATICALLY FLIP THE DETECTED COORDINATES
        corners = det.corners.astype(int)
        corners[:, 0] = W - corners[:, 0] 
        last_corners = corners
        
        center = det.center.astype(int)
        center[0] = W - center[0]         
        last_center = center
        
        last_id = det.tag_id
        last_family = det.tag_family.decode()
        frames_since_seen = 0
        confident = True
    else:
        frames_since_seen += 1
        confident = False

    # --- Visual Highlighting & Tag Mapping ---
    if last_center is not None and frames_since_seen < COASTING_FRAMES:
        cx, cy = last_center
        
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            tag_in_active_cell = True

        tag_color = (0, 255, 0) if confident else (0, 165, 255) 
        
        cv2.polylines(
            frame,
            [last_corners.reshape((-1, 1, 2))],
            True,
            tag_color,
            2,
        )
        cv2.circle(
            frame,
            tuple(last_center),
            5,
            (0, 0, 255) if confident else tag_color,
            -1,
        )

        status_text = f"{last_family} id={last_id}" if confident else f"Estimated id={last_id}"
        tx, ty = last_corners[0]
        cv2.putText(frame, status_text, (tx, ty - 10), cv2.FONT_HERSHEY_SIMPLEX, 
                    0.65, tag_color, 2, cv2.LINE_AA)
        
        if not tag_in_active_cell:
            tag_col = max(0, min(W - 1, cx)) // cell_w
            tag_row = max(0, min(H - 1, cy)) // cell_h
            cx1, cy1 = tag_col * cell_w, tag_row * cell_h
            cx2, cy2 = cx1 + cell_w, cy1 + cell_h
            cv2.rectangle(frame, (cx1, cy1), (cx2, cy2), (0, 255, 255), 2)


    for i in range(1, GRID_COLS):
        cv2.line(frame, (i * cell_w, 0), (i * cell_w, H), (150, 150, 150), 1)
    for i in range(1, GRID_ROWS):
        cv2.line(frame, (0, i * cell_h), (W, i * cell_h), (150, 150, 150), 1)


    active_color = (0, 255, 0) if tag_in_active_cell else (255, 0, 0)
    cv2.rectangle(frame, (x1, y1), (x2, y2), active_color, 4)


    cv2.putText(frame, f"LR Angle (X): {lr_angle} | UD Angle (Y): {ud_angle}", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    
    if tag_in_active_cell:
        cv2.putText(frame, "Target Locked! Adjust angles and press Enter.", (10, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    else:
        cv2.putText(frame, f"Move tag to active cell ({active_cell + 1}/{GRID_ROWS * GRID_COLS})", (10, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    cv2.imshow("AprilTag Detector", frame)


    key = cv2.waitKeyEx(1)
    if key in (ord("q"), 27): 
        break

    if tag_in_active_cell and key != -1:
        updated = False
        # Key detection snippet from gemini 
        if key in (63232, 2490368, ord('w'), ord('W')):    # Up
            if ud_angle < 45:
                ud_angle += 1
                updated = True
        elif key in (63233, 2621440, ord('s'), ord('S')):  # Down
            if ud_angle > 0:
                ud_angle -= 1
                updated = True
        elif key in (63234, 2424832, ord('a'), ord('A')):  # Left
            if lr_angle > 0:
                lr_angle -= 1
                updated = True
        elif key in (63235, 2555904, ord('d'), ord('D')):  # Right
            if lr_angle < 180:
                lr_angle += 1
                updated = True
            
        if updated:
            threading.Thread(target=send_serial_command, args=(lr_angle, ud_angle)).start()
            
 
        if key in (13, 10):
            record = {
                "cell_index": active_cell,
                "x_range": (x1, x2),
                "y_range": (y1, y2),
                "lr_angle": lr_angle,
                "ud_angle": ud_angle
            }
            recorded_data.append(record)
            print(f"-> Saved data for Cell {active_cell + 1}: {record}")
            
            active_cell += 1
            if active_cell >= GRID_ROWS * GRID_COLS:
                print("\n--- Grid Completed! ---")
                print("All recorded data:")
                for r in recorded_data:
                    print(r)
                break

camera.release()
cv2.destroyAllWindows()
if pico_serial:
    pico_serial.close()
