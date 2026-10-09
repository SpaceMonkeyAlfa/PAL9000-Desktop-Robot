import cv2
import serial
import time
import os
import math
import urllib.request
import numpy as np
from collections import deque
from pupil_apriltags import Detector


import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


CAMERA_INDEX = 0  
SERIAL_PORT = "/dev/cu.usbmodem1101" # <-- Update with the pico's serial port
BAUD_RATE = 115200

FRAME_W = 1280
FRAME_H = 720
CELL_W = FRAME_W / 5.0 
CELL_H = FRAME_H / 3.0  

UPDATE_INTERVAL = 0.1  # Send command every 0.1 seconds


TARGET_TAG_IDS = (42, 7)
target_tag_index = 0
TARGET_TAG_ID = TARGET_TAG_IDS[target_tag_index]
FACE_X_MARGIN = 250     # How far left/right of the tag a face can be
CROP_SIZE = 600         # A perfect square crop to prevent MediaPipe from squishing the image
COAST_TIME = 1.0        # Seconds to keep coasting/predicting after losing tag/face


try:
    pico_serial = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1, write_timeout=0)
    print(f"Successfully connected to Pico on {SERIAL_PORT}")
except Exception as e:
    print(f"WARNING: Could not open serial port {SERIAL_PORT}. Error: {e}")
    print("Running in display-only mode.")
    pico_serial = None

def send_serial_command(lr, ud):
    if pico_serial and pico_serial.is_open:
        try:
            command = f"{lr} {ud}\n"
            pico_serial.write(command.encode('utf-8'))
        except Exception:
            pass

# Face detector
MODEL_PATH = "face_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"

if not os.path.exists(MODEL_PATH):
    print(f"Downloading MediaPipe Face Landmarker model to {MODEL_PATH}...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    num_faces=4, #Max 4 faces (for now)
    min_face_detection_confidence=0.3,
    min_face_presence_confidence=0.3,
    min_tracking_confidence=0.3,
    output_face_blendshapes=False,
    output_facial_transformation_matrixes=False
)
face_landmarker = vision.FaceLandmarker.create_from_options(options)


detector = Detector(families="tag36h11", nthreads=4, quad_decimate=1.0, quad_sigma=0.0, refine_edges=1)

camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_AVFOUNDATION)
if not camera.isOpened():
    raise RuntimeError(f"Could not open camera index {CAMERA_INDEX}.")
camera.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

print(f"Starting Tracker. Looking for AprilTag ID: {TARGET_TAG_ID}")


last_update_time = time.time()
last_sent_lr = "N/A"
last_sent_ud = "N/A"

# Memory variables for Tag Coasting
last_tag_cx = None
last_tag_cy = None
last_tag_time = 0.0


face_history = deque(maxlen=10) 
last_face_w = 100
last_face_h = 100

while True:
    now = time.time()
    ok, frame = camera.read()
    if not ok: break


    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    detections = detector.detect(gray)


    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    

    for i in range(1, 5): cv2.line(frame, (int(i * CELL_W), 0), (int(i * CELL_W), FRAME_H), (100, 100, 100), 1)
    for i in range(1, 3): cv2.line(frame, (0, int(i * CELL_H)), (FRAME_W, int(i * CELL_H)), (100, 100, 100), 1)

  
    target_tag = None
    if detections:
        for det in detections:
            if det.tag_id == TARGET_TAG_ID:
                target_tag = det
                break

    tag_cx = None
    tag_cy = None
    is_tag_coasting = False

    if target_tag:
        corners = target_tag.corners.astype(int)
        corners[:, 0] = FRAME_W - corners[:, 0] 
        center = target_tag.center.astype(int)
        
        tag_cx = FRAME_W - center[0]
        tag_cy = center[1]

        last_tag_cx = tag_cx
        last_tag_cy = tag_cy
        last_tag_time = now

        cv2.polylines(frame, [corners.reshape((-1, 1, 2))], True, (0, 255, 0), 2)
        cv2.circle(frame, (tag_cx, tag_cy), 5, (0, 0, 255), -1)
    
    elif last_tag_cx is not None and (now - last_tag_time) <= COAST_TIME:
        tag_cx = last_tag_cx
        tag_cy = last_tag_cy
        is_tag_coasting = True
        cv2.circle(frame, (tag_cx, tag_cy), 5, (0, 165, 255), -1)

    # Face detection snippet from gemini
    active_face_x = None
    active_face_y = None
    is_face_predicted = False

    if tag_cx is not None and tag_cy is not None:
        
        # Crop square ROI around the tag
        roi_y_max = min(FRAME_H, tag_cy + 100)
        roi_y_min = max(0, roi_y_max - CROP_SIZE)
        roi_x_min = max(0, tag_cx - (CROP_SIZE // 2))
        roi_x_max = min(FRAME_W, tag_cx + (CROP_SIZE // 2))

        box_color = (0, 165, 255) if is_tag_coasting else (255, 255, 255)
        cv2.rectangle(frame, (roi_x_min, roi_y_min), (roi_x_max, roi_y_max), box_color, 1)

        faces = []
        if roi_y_max > roi_y_min and roi_x_max > roi_x_min:
            roi_rgb = rgb_frame[roi_y_min:roi_y_max, roi_x_min:roi_x_max].copy()
            roi_h, roi_w, _ = roi_rgb.shape
            
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=roi_rgb)
            landmarker_results = face_landmarker.detect(mp_image)

            if landmarker_results.face_landmarks:
                for face_landmarks in landmarker_results.face_landmarks:
                    x_coords = [landmark.x * roi_w for landmark in face_landmarks]
                    y_coords = [landmark.y * roi_h for landmark in face_landmarks]
                    
                    x = int(min(x_coords)) + roi_x_min
                    y = int(min(y_coords)) + roi_y_min
                    w = int(max(x_coords) - min(x_coords))
                    h = int(max(y_coords) - min(y_coords))
                    
                    fcx = x + (w // 2)
                    fcy = y + (h // 2)
                    faces.append((x, y, w, h, fcx, fcy))
                    
                    # Draw blue rectangle around all candidates
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

        # Match closest face to the tag 
        best_face = None
        min_distance = float('inf')
        for face in faces:
            fx, fy, fw, fh, fcx, fcy = face
            
 
            if fcy < tag_cy + 50 and abs(fcx - tag_cx) <= FACE_X_MARGIN:
                
 
                distance = math.hypot(fcx - tag_cx, fcy - tag_cy)
                
                if distance < min_distance:
                    min_distance = distance
                    best_face = face


        if best_face:
            fx, fy, fw, fh, fcx, fcy = best_face
            active_face_x, active_face_y = fcx, fcy
            last_face_w, last_face_h = fw, fh

            face_history.append((now, fcx, fcy))


            cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (0, 255, 0), 3)
            cv2.circle(frame, (fcx, fcy), 5, (0, 255, 0), -1)
            cv2.line(frame, (tag_cx, tag_cy), (fcx, fcy), (0, 255, 255), 2)

        # --- B. FACE LOST: 10-FRAME TRAJECTORY PREDICTION ---
        elif len(face_history) >= 2 and (now - face_history[-1][0]) <= COAST_TIME:
            is_face_predicted = True
            
            # 1. Compute velocity across the available history window (up to 10 frames)
            t_old, x_old, y_old = face_history[0]
            t_new, x_new, y_new = face_history[-1]
            dt_history = t_new - t_old

            if dt_history > 0.001:
                vx = (x_new - x_old) / dt_history  # pixels / second
                vy = (y_new - y_old) / dt_history  # pixels / second

                # 2. Extrapolate position based on elapsed time since the face was last seen
                time_lost = now - t_new
                pred_x = int(x_new + (vx * time_lost))
                pred_y = int(y_new + (vy * time_lost))

                # Clamp prediction to frame boundaries
                active_face_x = max(0, min(FRAME_W, pred_x))
                active_face_y = max(0, min(FRAME_H, pred_y))

                # Draw predicted bounding box & trail (Magenta / Purple)
                px = active_face_x - (last_face_w // 2)
                py = active_face_y - (last_face_h // 2)
                cv2.rectangle(frame, (px, py), (px + last_face_w, py + last_face_h), (255, 0, 255), 2)
                cv2.putText(frame, "PREDICTED", (px, py - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
                cv2.circle(frame, (active_face_x, active_face_y), 5, (255, 0, 255), -1)
                cv2.line(frame, (tag_cx, tag_cy), (active_face_x, active_face_y), (255, 0, 255), 2)

        else:
            # If face has been gone for too long, reset the trajectory history
            if len(face_history) > 0 and (now - face_history[-1][0]) > COAST_TIME:
                face_history.clear()


    if active_face_x is not None and active_face_y is not None:
        if now - last_update_time >= UPDATE_INTERVAL:
            grid_y = (active_face_x / CELL_W) - 0.5 
            grid_x = (active_face_y / CELL_H) - 0.5 
            
            grid_y = max(0.0, min(4.0, grid_y))
            grid_x = max(0.0, min(2.0, grid_x))
            
            # LOBFs (edit these with your calibration LOBFs)
            target_ud = 5 * (grid_x**2) + grid_x + 3
            target_lr = -1.429 * (grid_y**2) + 20.71 * grid_y + 110

            final_lr = int(max(0, min(180, round(target_lr))))
            final_ud = int(max(0, min(180, round(target_ud))))

            send_serial_command(final_lr, final_ud)
            last_sent_lr = final_lr
            last_sent_ud = final_ud
            last_update_time = now


    for i in range(len(face_history)):
        _, hx, hy = face_history[i]
        cv2.circle(frame, (hx, hy), 2, (255, 255, 0), -1)


    cv2.putText(frame, f"Sent LR: {last_sent_lr} | Sent UD: {last_sent_ud}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    
    if is_face_predicted:
        time_left = max(0.0, COAST_TIME - (now - face_history[-1][0]))
        cv2.putText(frame, f"Face Lost! Predicting Trajectory: {time_left:.1f}s", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
    elif is_tag_coasting:
        time_left = max(0.0, COAST_TIME - (now - last_tag_time))
        cv2.putText(frame, f"Tag Lost! Coasting: {time_left:.1f}s", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
    elif target_tag is None:
        cv2.putText(frame, f"Searching for AprilTag ID: {TARGET_TAG_ID}...", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    else:
        cv2.putText(frame, f"Tracking Tag ID: {TARGET_TAG_ID}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow("Tracker", frame)

    key = cv2.waitKeyEx(1) & 0xFF

    if key in (ord("q"), 27):
        break

    elif key in (13, 10): 
        target_tag_index = (target_tag_index + 1) % len(TARGET_TAG_IDS)
        TARGET_TAG_ID = TARGET_TAG_IDS[target_tag_index]


        last_tag_cx = None
        last_tag_cy = None
        last_tag_time = 0.0
        face_history.clear()

        print(f"Now tracking AprilTag ID: {TARGET_TAG_ID}")

camera.release()
face_landmarker.close()
cv2.destroyAllWindows()
if pico_serial: pico_serial.close()
