import os
import sys
from flask import Flask, render_template

app = Flask(__name__, template_folder="templates", static_folder="static")

# Set the IP or hostname of your Main PC here (e.g. 192.168.1.50)
MAIN_SERVER_HOST = os.environ.get("MAIN_SERVER_HOST", "192.168.1.100")
MAIN_SERVER_PORT = "5000"

@app.route("/")
def index():
    server_url = f"http://{MAIN_SERVER_HOST}:{MAIN_SERVER_PORT}"
    return render_template("index.html", server_url=server_url)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        MAIN_SERVER_HOST = sys.argv[1]
    print(f"[*] Targeting Main Assistant Server at: http://{MAIN_SERVER_HOST}:{MAIN_SERVER_PORT}")
    print("[+] Running client host at http://localhost:8000")
    app.run(host="127.0.0.1", port=8000, debug=False)
