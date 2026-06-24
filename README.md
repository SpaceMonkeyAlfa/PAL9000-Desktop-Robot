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
The first stage of the project was to implement a simple, cute face which could "see" using the phone's camera, and follow faces with its eyes. You can read up on my process [here on my blog](). It displays best on mobile in fullscreen, which you can activate by clicking anywhere on the page. By default, the camera stream is hidden, but this can lead to issues in some browsers. To show the webcam stream, just append `?show-stream` to the URL, or [click here](url). 

<img width="600" height="315" alt="image" src="https://github.com/user-attachments/assets/06283b2e-fc8a-4b90-b1c1-77f0917739e0" />


## Running
For now, the project runs entirely in a web browser. You can test out the demo [here]() on github pages, or download the repo, and host it with `python3 -m http.server` or any basic http / https server.
