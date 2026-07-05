# PAL9000 Desktop Robot
After shopping around for various electronic components, I’ve seen some really cool “desktop robot” projects. In need of a new project, I decided to build my own.

The robot would stay on top of a desk, with an LCD for a face, and a “neck” which would allow it to turn left and right, up and down. It would have a camera and microphone, allowing it to see its surroundings, and interact with people. For a proof of concept, I wanted the bot to be able to:

* Use a camera for face tracking

* Follow faces with its eyes and neck

* Display cute expressions, which respond in real time

* Transcribe voices to understand tasks

* Be able to forward tasks to various APIs or AI providers

To make this project accesible and afordable, the robot will use an old android phone as it's "brain". As I work on this project, I'll publish my progress and howtos on my blog, [spacemonkeyalfa.com](spacemonkeyalfa.com), and make all of the code open source in this repo.

## Face Tracking Demo
The first stage of the project was to implement a simple, cute face which could "see" using the phone's camera, and follow faces with its eyes. You can read up on my process [here on my blog](https://spacemonkeyalfa.com/post/2026/06/24/building-a-robot-face/). It displays best on mobile in fullscreen, which you can activate by clicking anywhere on the page. By default, the camera stream is hidden, but this can lead to issues in some browsers. To show the webcam stream, just append `?show-stream` to the URL, or [click here](https://spacemonkeyalfa.github.io/PAL9000-Desktop-Robot?show-stream). 

<img width="600" height="315" alt="image" src="https://github.com/user-attachments/assets/06283b2e-fc8a-4b90-b1c1-77f0917739e0" />

For now, the face tracking demo runs entirely in a web browser. You can test out the demo [here](https://spacemonkeyalfa.github.io/PAL9000-Desktop-Robot/) on github pages, or download the repo, and host it with `python3 -m http.server` or any basic http / https server.

## Servo Demo
In my second [blog post](spacemonkeyalfa.com), I talked about how I connected my phone to a Pi Pico W over WiFi to control a servo in real time, based on my face position. You can read about it [here](spacemonkeyalfa.com), or watch it working on [youtube here](https://youtu.be/xJCiOsIxeKs).

https://github.com/user-attachments/assets/483e0fb6-32ff-43a3-b586-3de6518e2c11

To run this project, you'll need an android phone running `termux`, a Pi Pico W, and a SG90 servo. 

**On the Pico W**
1) Flash micropython to it
2) Install this [servo library](https://github.com/redoxcode/micropython-servo), following the README's install instructions
3) Copy the `pico/main.py` script into the root path of the pico
4) Edit the `WifiSSD` and `WifiPWD` to match your WiFi's name and password
5) Run the script by placing your cursor into the serial terminal, and pressing `Ctrl+D`
6) The Pico's local IP should print to the serial terminal
7) Connect the SG90's positive terminal to the Pico's VBUS, the negative terminal to the GND, and the signal to GP0

**On the phone**
1) Install python
2) Clone this repo
3) Edit `index.html`'s `PicoURL` variable to match the Pico's local IP
4) Run `python3 -m http.server 8080 `
5) Open `localhost:8080` in the browser
6) Click anywhere on screen



   
