import base64
from time import sleep
from collections import deque
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import tempfile
import threading
import uuid
import numpy as np
import requests
import scipy.io.wavfile as wav
import sounddevice as sd
import torch
from openai import OpenAI
from registry import TOOLS, SCHEMAS 
import cal

from flask import Flask, send_from_directory
from flask_socketio import SocketIO

app = Flask(__name__)
app.config["SECRET_KEY"] = "pal9000-secret"
# cors_allowed_origins="*" allows Termux client (port 8000) to connect
socketio = SocketIO(app, cors_allowed_origins="*")

AUDIO_DIR = Path("./static/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

client_capture_queue = queue.Queue()

@app.route("/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

@socketio.on("client_frame")
def handle_client_frame(data):
    """Received snapshot from the client device's browser."""
    b64_img = data.get("image")
    client_capture_queue.put(b64_img)

def capture_frame_from_client(timeout_s: float = 4.0) -> str:
    print("[*] Requesting camera frame from remote client...")
    while not client_capture_queue.empty():
        try:
            client_capture_queue.get_nowait()
        except queue.Empty:
            break

    socketio.emit("request_capture")

    try:
        b64_image = client_capture_queue.get(timeout=timeout_s)
        if b64_image:
            print("[+] Successfully received frame from client.")
            return b64_image
    except queue.Empty:
        print("[!] Client frame capture timed out.")

    return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

LLAMA_SERVER_URL = "http://127.0.0.1:8080/v1"

client = OpenAI(
    base_url=LLAMA_SERVER_URL,
    api_key="not-needed",
)
WHISPER_DIR = Path("./whisper.cpp")
WHISPER_BIN_DIR = WHISPER_DIR / "build" / "bin"

TRIAGE_PROMPT = (
    "You are a robot assistant named PAL9000, built by SpaceMonkeyAlfa. "
    "Attached is a transcription of a user's input, along with an image capture of the user. "
    "You have also been provided with a set of tools to connect with other applications. "
    "If you feel for any reason that you are unable to facilitate the user's request explain to the user that you can't. "
    "When using calendar functionality, if the user hasn't provided you with all the information you need ASK first. "
    "If asked to edit an event, first use the read tool to list all events and IDs, then use the delete tool to delete the old event, then create a new event with the corrected data."
    "Your output will be turned into speech with TTS, so keep your responses short and conversational. Remove markdown formatting."
    "You do not need to introduce yourself unless the user asks you to."
    "Your responses will automatically start with an acknowledgement such as 'yep', so no need to use them yourself."
)

print("Loading Silero VAD model...")
torch.set_num_threads(1)
try:
    vad_model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        trust_repo=True,
    )
    VADIterator = utils[3]
except Exception:
    from silero_vad import load_silero_vad, VADIterator
    vad_model = load_silero_vad()

vad_model.eval()


def record_audio_to_file(sample_rate: int = 16000, max_speech_s: float = 30.0) -> str:
    chunk_size = 512
    vad_iterator = VADIterator(
        model=vad_model,
        threshold=0.5,
        sampling_rate=sample_rate,
        min_silence_duration_ms=2000,
        speech_pad_ms=200,
    )
    vad_iterator.reset_states()

    audio_queue = queue.Queue()

    def audio_callback(indata, frames, time_info, status):
        if status:
            print(f"\nAudio status warning: {status}", flush=True)
        audio_queue.put(indata[:, 0].copy())

    pre_speech_chunks = int(0.5 * sample_rate / chunk_size)
    pre_buffer = deque(maxlen=pre_speech_chunks)
    recorded_chunks = []
    is_speaking = False

    print("[*] Listening on server microphone... Speak when ready (Ctrl+C to quit)", flush=True)

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        blocksize=chunk_size,
        callback=audio_callback,
    ):
        while True:
            chunk = audio_queue.get()
            chunk_tensor = torch.from_numpy(chunk)
            vad_event = vad_iterator(chunk_tensor)

            if not is_speaking:
                pre_buffer.append(chunk)
                if vad_event and "start" in vad_event:
                    is_speaking = True
                    print("[+] Speech detected! Recording...", flush=True)
                    recorded_chunks.extend(pre_buffer)
                    pre_buffer.clear()
            else:
                recorded_chunks.append(chunk)
                if vad_event and "end" in vad_event:
                    print("[-] 3 seconds of silence detected. Stopping recording.", flush=True)
                    break
                recorded_duration = (len(recorded_chunks) * chunk_size) / sample_rate
                if recorded_duration >= max_speech_s:
                    print(f"[-] Reached maximum limit ({max_speech_s}s). Stopping recording.", flush=True)
                    break

    if not recorded_chunks:
        raise RuntimeError("No audio frames were captured.")

    audio_float = np.concatenate(recorded_chunks, axis=0)
    audio_int16 = (np.clip(audio_float, -1.0, 1.0) * 32767).astype(np.int16)

    temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav.write(temp_wav.name, sample_rate, audio_int16)
    return temp_wav.name


def transcribe_audio_whisper(wav_path: str) -> str:
    whisper_cli = WHISPER_BIN_DIR / "whisper-cli"
    if not whisper_cli.exists():
        whisper_cli = WHISPER_BIN_DIR / "main"

    models = list(WHISPER_DIR.glob("models/ggml-*.bin"))
    preferred = [m for m in models if "base.en" in m.name or "tiny.en" in m.name]
    model_path = preferred[0] if preferred else models[0]

    cmd = [
        str(whisper_cli),
        "-m", str(model_path),
        "-f", wav_path,
        "-nt", "--no-prints",
    ]

    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=True
        )
        transcript = proc.stdout.strip()
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

    transcript = re.sub(r"\[.*?\]", "", transcript).strip()
    print(f'Transcribed: "{transcript}"')
    return transcript


def send_chat_turn(history: list, transcript: str, image_b64: str) -> tuple[str, bool]:
    user_turn_content = f'{TRIAGE_PROMPT}\n\nUser input: "{transcript}"'
    history.append({
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            {"type": "text", "text": user_turn_content},
        ],
    })

    used_tool = False

    while True:
        print("Querying llama-server...")
        try:
            response = client.chat.completions.create(
                model="local-model",
                messages=history,
                tools=SCHEMAS,
                tool_choice="auto",
                temperature=0.1,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Could not reach llama-server at {LLAMA_SERVER_URL}.")

        message = response.choices[0].message
        if message.tool_calls:
            # First tool call encountered: bring up the book!
            if not used_tool:
                used_tool = True
                print("[*] Tool usage detected. Displaying book.svg...")
                socketio.emit("show_book")

            history.append(message.model_dump())
            for call in message.tool_calls:
                name = call.function.name
                args = json.loads(call.function.arguments or "{}")
                try:
                    result = TOOLS[name](**args)
                except Exception as e:
                    result = {"error": str(e)}

                history.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                })
            continue

        result_text = message.content.strip() if message.content else ""
        history.append({"role": "assistant", "content": result_text})
        return result_text, used_tool


def save_tts_and_notify_client(response_text: str):
    clean_text = response_text.strip()
    if "<think>" in clean_text and "</think>" in clean_text:
        clean_text = clean_text.split("</think>")[-1].strip()

    print("\n" + "=" * 50 + f"\nMODEL OUTPUT:\n{clean_text}\n" + "=" * 50 + "\n")
    if not clean_text:
        return

    filename = f"tts_{uuid.uuid4().hex[:8]}.wav"
    output_path = AUDIO_DIR / filename

    print(f"[*] Rendering TTS to {output_path}...")
    cmd = [
        "say", "-o", str(output_path),
        "--file-format=WAVE",
        "--data-format=LEI16@22050",
        clean_text
    ]
    subprocess.run(cmd, check=True)

    socketio.emit("play_audio", {"url": f"/audio/{filename}", "text": clean_text})

    samplerate, data = wav.read(output_path)
    length = data.shape[0] / samplerate

    return int(length)


def assistant_loop():
    conversation_history = []
    turn_count = 1

    print("==================================================")
    print(" PAL Hands-Free VAD")
    print("==================================================")

    while True:
        try:
            wav_path = record_audio_to_file()
            print("Telling phone to say yep...")
            socketio.emit("play_ack")
            transcript = transcribe_audio_whisper(wav_path)

            if not transcript:
                print("[!] Whisper heard nothing. Please try speaking again.")
                continue

            # Capture webcam from the remote client browser
            image_b64 = capture_frame_from_client()
            output, used_tool = send_chat_turn(conversation_history, transcript, image_b64)
            sleep(save_tts_and_notify_client(output)+2)

            turn_count += 1
        except Exception as e:
            print(f"\n[!] Error during turn {turn_count}: {e}")


def main():
    threading.Thread(target=assistant_loop, daemon=True).start()
    print("\n[+] Main Assistant server listening on 0.0.0.0:5000\n")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
