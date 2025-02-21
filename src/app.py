from flask import Flask, render_template, request, redirect, url_for, send_from_directory
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
        config["TEST"] = request.form.get("TEST") == "on"
        config["ALL_DRAWINGS"] = request.form.get("ALL_DRAWINGS") == "on"
        config["SKIP_CREATOR"] = request.form.get("SKIP_CREATOR") == "on"
        config["INFER_BHL_PAGE_FROM_FLICKR_ID"] = request.form.get("INFER_BHL_PAGE_FROM_FLICKR_ID") == "on"
        config["INFER_FROM_INTERNET_ARCHIVE"] = request.form.get("INFER_FROM_INTERNET_ARCHIVE") == "on"
        try:
            config["INTERNET_ARCHIVE_OFFSET"] = int(request.form.get("INTERNET_ARCHIVE_OFFSET", "-1"))
        except ValueError:
            config["INTERNET_ARCHIVE_OFFSET"] = -1
        config["PHOTOGRAPHS_ONLY"] = request.form.get("PHOTOGRAPHS_ONLY") == "on"
        config["ILLUSTRATOR"] = request.form.get("ILLUSTRATOR", "").strip()
        config["PAINTER"] = request.form.get("PAINTER", "").strip()
        config["ENGRAVER"] = request.form.get("ENGRAVER", "").strip()
        config["LITHOGRAPHER"] = request.form.get("LITHOGRAPHER", "").strip()
        config["REF_URL_FOR_AUTHORS"] = request.form.get("REF_URL_FOR_AUTHORS", "").strip()
        config["COMMONS_API_ENDPOINT"] = request.form.get("COMMONS_API_ENDPOINT", "").strip()
        config["WIKIDATA_SPARQL_ENDPOINT"] = request.form.get("WIKIDATA_SPARQL_ENDPOINT", "").strip()
        config["BHL_BASE_URL"] = request.form.get("BHL_BASE_URL", "").strip()
        config["SET_PROMINENT"] = request.form.get("SET_PROMINENT") == "on"
        config["SKIP_PUBLISHED_IN"] = request.form.get("SKIP_PUBLISHED_IN") == "on"
        config["SKIP_DATES"] = request.form.get("SKIP_DATES") == "on"
        config["ADD_EMPTY_IF_SPONSOR_MISSING"] = request.form.get("ADD_EMPTY_IF_SPONSOR_MISSING") == "on"
        config["SKIP_EXISTING_INSTANCE_OF"] = request.form.get("SKIP_EXISTING_INSTANCE_OF") == "on"

        # Save the updated configuration
        save_config(config)

        # Compute CATEGORY_NAME from CATEGORY_RAW
        CATEGORY_NAME = config["CATEGORY_RAW"].replace("_", " ").replace("Category:", "").strip()

        data = get_metadata.generate_metadata(CATEGORY_NAME, app_mode=True)
        output_file = DATA / f"{CATEGORY_NAME.replace(' ', '_')}.tsv"
        df = pd.DataFrame(data)
        df.to_csv(output_file, sep="\t", index=False)
        # Pass the metadata to the result template for display.
        message = f"Data written to: {output_file}"
        return render_template("index.html", config=config, message=message, output_file=output_file.name)

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
    config["TEST"] = request.form.get("TEST") == "on"
    config["ALL_DRAWINGS"] = request.form.get("ALL_DRAWINGS") == "on"
    config["SKIP_CREATOR"] = request.form.get("SKIP_CREATOR") == "on"
    config["INFER_BHL_PAGE_FROM_FLICKR_ID"] = request.form.get("INFER_BHL_PAGE_FROM_FLICKR_ID") == "on"
    config["INFER_FROM_INTERNET_ARCHIVE"] = request.form.get("INFER_FROM_INTERNET_ARCHIVE") == "on"
    try:
        config["INTERNET_ARCHIVE_OFFSET"] = int(request.form.get("INTERNET_ARCHIVE_OFFSET", "-1"))
    except ValueError:
        config["INTERNET_ARCHIVE_OFFSET"] = -1
    config["PHOTOGRAPHS_ONLY"] = request.form.get("PHOTOGRAPHS_ONLY") == "on"
    config["ILLUSTRATOR"] = request.form.get("ILLUSTRATOR", "").strip()
    config["PAINTER"] = request.form.get("PAINTER", "").strip()
    config["ENGRAVER"] = request.form.get("ENGRAVER", "").strip()
    config["LITHOGRAPHER"] = request.form.get("LITHOGRAPHER", "").strip()
    config["REF_URL_FOR_AUTHORS"] = request.form.get("REF_URL_FOR_AUTHORS", "").strip()
    config["COMMONS_API_ENDPOINT"] = request.form.get("COMMONS_API_ENDPOINT", "").strip()
    config["WIKIDATA_SPARQL_ENDPOINT"] = request.form.get("WIKIDATA_SPARQL_ENDPOINT", "").strip()
    config["BHL_BASE_URL"] = request.form.get("BHL_BASE_URL", "").strip()
    config["SET_PROMINENT"] = request.form.get("SET_PROMINENT") == "on"
    config["SKIP_PUBLISHED_IN"] = request.form.get("SKIP_PUBLISHED_IN") == "on"
    config["SKIP_DATES"] = request.form.get("SKIP_DATES") == "on"
    config["ADD_EMPTY_IF_SPONSOR_MISSING"] = request.form.get("ADD_EMPTY_IF_SPONSOR_MISSING") == "on"
    config["SKIP_EXISTING_INSTANCE_OF"] = request.form.get("SKIP_EXISTING_INSTANCE_OF") == "on"

    # Save the updated configuration
    save_config(config)

    # Execute the upload.py script
    subprocess.run(["python3", "upload.py"])
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)