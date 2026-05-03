from flask import Flask
import os
import subprocess

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot alive"

@app.route("/run")
def run_bot():
    subprocess.run(["python", "main.py"])
    return "ok"
