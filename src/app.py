from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
)
import get_metadata  # This is your module (get_metadata.py) that contains generate_metadata()
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm
from login import *
import json
import subprocess

# Directories for data and dictionaries
HERE = Path(__file__).parent
DATA = HERE / "data"
DICTS = HERE / "dicts"
API_CACHE = {}
app = Flask(__name__)


# Load configuration from config.json
def load_config():
    with open(HERE / "config.json", "r") as config_file:
        return json.load(config_file)


# Save configuration to config.json
def save_config(config):
    with open(HERE / "config.json", "w") as config_file:
        json.dump(config, config_file, indent=4)


@app.route("/", methods=["GET", "POST"])
def index():
    config = load_config()
    if request.method == "POST":
        # Read form data
        config["CATEGORY_RAW"] = request.form.get("CATEGORY_RAW", "").strip()
        CATEGORY_NAME = (
            config["CATEGORY_RAW"].replace("_", " ").replace("Category:", "").strip()
        )
        output_file = DATA / f"{CATEGORY_NAME.replace(' ', '_')}.tsv"
        subprocess.run(
            [
                "python3",
                "get_metadata.py",
                "--auto_mode",
                "--category_raw",
                config["CATEGORY_RAW"],
            ]
        )
        # Pass the metadata to the result template for display.
        message = f"Data written to: {output_file}"
        return render_template(
            "index.html", config=config, message=message, output_file=output_file.name
        )

    # GET request: render the form.
    return render_template("index.html", config=config)


@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(DATA, filename, as_attachment=True)


@app.route("/upload", methods=["POST"])
def upload():
    config = load_config()
    # Read form data
    config["CATEGORY_RAW"] = request.form.get("CATEGORY_RAW", "").strip()
    # python3 upload.py --auto_mode --category_raw "$CATEGORY_RAW"
    subprocess.run(
        [
            "python3",
            "upload.py",
            "--auto_mode",
            "--category_raw",
            config["CATEGORY_RAW"],
        ]
    )
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
