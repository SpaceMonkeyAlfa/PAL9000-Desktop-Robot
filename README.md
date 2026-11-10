# PAL9000 Desktop Robot

[![Demo Video](https://github.com/user-attachments/assets/94a80abf-6ac3-4fcf-b8c1-05329994e51a)](https://www.youtube.com/watch?v=wm2kRotLKiM)

Python driven gimbal robot. 2 DOF, powered by a Pico W. Face tracking from a mobile phone. Follows voice and visual cues. Processed locally. 

After shopping around for various electronic components, I’ve seen some really cool “desktop robot” projects. In need of a new project, I decided to build my own.

The robot would stay on top of a desk, with an LCD for a face, and a “neck” which would allow it to turn left and right, up and down. It would have a camera and microphone, allowing it to see its surroundings, and interact with people. For a proof of concept, I wanted the bot to be able to:

- Use a camera for face tracking
    
- Follow faces with its eyes and neck
    
- Display cute expressions, which respond in real time
    
- Transcribe voices to understand tasks
    
- Be able to forward tasks to various APIs or AI providers
    

To make this project accessible and affordable, the robot will use an old android phone as it's "brain". As I work on this project, I'll publish my progress and howtos on my blog, [spacemonkeyalfa.com](https://github.com/SpaceMonkeyAlfa/PAL9000-Desktop-Robot/blob/main/spacemonkeyalfa.com), and make all of the code open source in this repo.

# Setup Guide

This project relies on a lot of pieces of code, running on multiple devices. It's admittedly a bit of a cludge right now, but in the future I plan to make the install and running process simpler, so start the repo if you're interested. 

To run this project, you'll need an android phone running `termux`, a webcam, a Mac / MacBook, a Pi Pico W, and a Gimbal robot with 2 degrees of freedom (DOF). You can find a lot of parts and kits for these robots from aliexpress. 

## Robot & Pico

This guide assumes you have some experience with hobbyist electronics. It's up to you to find a way to power the servos of the robot (keep in mind they're pretty high current), though [this article from my blog](https://spacemonkeyalfa.com/post/2026/10/09/controlling-robot-joints-with-computer-vision/#:~:text=Wiring%20the%20New%20Gimbal%20Body) explains how I set mine up. You want your pico's ground pin to be connected in parallel to your power source's, and have the control pins of both servos wired to GP0 and GP1. 

On the pico, flash `micropython`, and then with a `micropython` IDE add `pico/main.py` (which you'll find in this repo). I'd suggest using either [Thonny](https://thonny.org/) or [ViperIDE](https://viper-ide.org/). If you set your wiring up right, as soon as you disconnect and reconnect your pico to power, the robot's head should jolt up to its (0,0). 

## MacBook

The MacBook side of things is probably the messiest, due to the deadlines and feature set I was rushing to meet. It needs to be a MacBook for now because the robot uses the `say` command for TTS. In future, I'm going to write a bash script to run all of the servers together, so you won't need 4 terminal sessions open. I also plan to add `espeak-ng` as an alternative to `say`, so you won't be limited to macOS. 

If you haven't already, install `homebrew`. Install `llama-cpp` using `brew install lamma-cpp`. Also install `ffmpeg` with `brew install ffmpeg`, portaudio with `brew install portaudio` and python with `brew install python3.13`. Make sure that you're on `python3.13`, because some of the libraries I used break with other python versions. 

Download both `laptop/llm-server` and `laptop/robot-controller` from this repo. Move these to any directory you want, but keep their contents separate. 

1) cd into `llm-server`
2) run `python3 -m venv venv` to set up a new virtual environment ('venv')
3) run `source venv/bin/activate` to activate the venv
4) run `pip3 install -r requirements.txt`
5) run `deactivate` 
6) cd back to the parent directory
7) cd into `robot-controller`
8) repeat steps 2-4 (don't run deactivate!) inside `robot controller`

Now that both the server and controller are set up, you'll need to calibrate your robot. Print out [this AprilTag](https://github.com/AprilRobotics/apriltag-imgs/blob/master/tag36h11/tag36_11_00042.png) (36h11 #42). Plug your webcam and pico into the MacBook. 
1) Find the serial port being used by the pico: `ls /dev/cu.usb*`. 
2) For both `calibrate.py` and `track.py`, update the `SERIAL_PORT` variables to match the serial port being used by the pico
3) Connect a bluetooth keyboard to the macbook.
4) Use `python3 calibrate.py` to start the calibration
5) Hold the AprilTag up to your face and move to the highlighted cell from the web cam feed
6) Once you're in that cell, use WASD on the bluetooth keyboard to control the robot, until it faces the AprilTag
7) Press enter, and a new cell will be highlighted. Move the AprilTag to the highlighted cell.
8) Repeat this process until the program finishes
9) The program should spit out two formulas that'll look something like this, copy them
```
	target_ud = 15 * (grid_x**2) + 12  
	target_lr = -0.5 * (grid_y**2) + 16.5 * grid_y + 25
```
	
1) Open `track.py`, find the comment that says 
 ` LOBFs (edit these with your calibration LOBFs)`
 2) Replace the two lines under it with the formulas you copied.
 3) Stick the AprilTag to your chest
 4) Use `python3 track.py` to start the tracker
 5) The robot should be able to follow you around

Now to set up the LLM server, open a new terminal session and cd into the `llm-server` directory. 
1) Follow `whisper-cpp`'s quickstart guide on downloading and building `whisper-cpp`
2) If you did that right, you should end up with a `whisper-cpp` folder inside your `llm-server` directory
3) Run `ipconfig getifaddr en0` to get your local IP, and note it for later
4) Run `source venv/bin/activate` to activate the virtual environment you set up earlier
5) If you want the google calendar integration (as show in the demo):
	1) Download `extra-tools/cal.py` from this repo and put it in the main `llm-server` directory
	2) Using Google Cloud, set up a project, and a service account with the default role
	3) Download the json auth file from the service account, and rename it to `serv-acc.json`, put this in the root `llm-server` directory
	4) Enable the google calendar API in the Google Cloud project
	5) Create a new calendar in Google Calendar, and share it with the service account (make sure to give it edit permissions)
	6) Update the `CALENDAR_ID` variable in `cal.py` to match the new shared calendar
	7) On line 18, update the `TIMEZONE` value to match your local timezone 
6) Run `python3 app.py` to run the server
7) Open another teminal session, and start the llama-cpp server 
```
llama-server \ 
-hf unsloth/gemma-4-12B-it-qat-GGUF:UD-Q4_K_XL \ 
--jinja \ 
-ngl 999 \ 
-c 16384 \ 
-fa on \ 
--host 127.0.0.1 \ 
--port 8080
```
Note the model may take a while to download the first time you run this, so wait for the download to complete before speaking. If you don't have enough unified memory (16GB+) to run `gemma4:12b` at 4b precision, or would like to use another model, just replace `unsloth/gemma-4-12B-it-qat-GGUF:UD-Q4_K_XL` with any huggingface gguf model.
## Phone

Find some way to mount your phone to the "face" of your gimbal robot. `mount/mounting_plate.stl` is a 3D printable plate designed to connect to most 2 DOF robots. Push some 3mm bolts through the mounting plate, so that their heads sit inside its wells. Fill the wells with blue tack to prevent superglue leaking. Then glue the well-side of the plate to the back of a phone case. By pushing the bolts sticking out of the phone case and mount through the front of the robot, you'll be able to tighten some nuts on the opposite side to attach the phone case to the robot. 

Install `termux`. I'd suggest installing it through `f-droid`, since the google play version is old and breaks some packages. 

1) Download the `phone` directory from this repo into `termux`.  
2) Run `pkg install python3`
3) Run `pip3 install flask`
4) Make sure your phone and the MacBook are on the same WiFi network
5) Run `python3 app.py {MacBook IP}`, replacing `{MacBook IP}` with the local IP address you got from the MacBook earlier.

Congratulations! If all went well, you should have a fully working robot, that can track, listen and speak to you as you move around the room.

# Troubleshooting

If the `track.py` suddenly crashes, it's often because your webcam connection has been disconnected. Similar for `llm-server/app.py`, if your microphone disconnects. 

If the robot's tracking is unresponsive, check if `track.py`'s log has this warning:
```
WARNING: Could not open serial port /dev/cu.usbmodem1101
```
this means that the pico is either disconnected, busy (ie `thonny` or `ViperIDE` is connected to it), or has connected on a different port. Once you're sure the pico's not busy, and is plugged in, simply run `ls /dev/cu.usb*` to get the new serial port, and update `track.py`. To avoid having to update the serial port each time, try to always use the same physical port for the pico. 

If the bot is taking a long time to respond, and you don't see any errors in `llm-server/app.py`, it might be that `llama-cpp` is just waiting for some memory to be freed up, to load the model's weights in. You can free this memory up yourself by just closing apps open in the background. Generation might also be slowed if you're on Low Power mode, so keep that off.

# Adding your own tools

PAL uses a modular system to handle tools. If you want to add your own tools, use `extra-tools/cal.py` as an example. The basics are to:

1) Have `from registry import tool` in your imports
2) Use the `@tool` decorator above your function
3) Include a docstring comment in your function to explain its purpose
4) Set the types for the function's inputs
5) Place the script containing your tool function in the main `llm-server` directory
6) Include `import {script_name}` in the imports at the top of `llm-server/app.py`, replacing `{script_name}` with the name of your tool script (without the .py extension)

# Changing the system prompt

To change PAL's system prompt, just edit the multi line `TRIAGE_PROMPT` variable in `llm-server/app.py`
