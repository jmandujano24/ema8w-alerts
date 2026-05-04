from flask import Flask
import subprocess

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot alive"

@app.route("/run")
def run_bot():
    result = subprocess.run(
        ["python", "main.py"],
        capture_output=True,
        text=True
    )

    return (
        f"returncode={result.returncode}\n\n"
        f"stdout:\n{result.stdout}\n\n"
        f"stderr:\n{result.stderr}"
    )
