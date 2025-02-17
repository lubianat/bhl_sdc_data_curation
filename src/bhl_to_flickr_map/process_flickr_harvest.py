import requests
import zipfile
import json
import csv
from pathlib import Path
HERE = Path(__file__).parent
# Define base directories
base_dir = HERE
zip_dir = base_dir / "zips"
extracted_dir = base_dir / "extracted"
tsv_dir = base_dir / "tsv"

# Create directories if they don't exist
zip_dir.mkdir(parents=True, exist_ok=True)
extracted_dir.mkdir(parents=True, exist_ok=True)
tsv_dir.mkdir(parents=True, exist_ok=True)

# List of zip file URLs (using raw GitHub URLs)
zip_urls = [
    "https://raw.githubusercontent.com/gbhl/bhl-us-data-sets/master/Flickr-Harvest/BHLFlickrDetails1.zip",
    "https://raw.githubusercontent.com/gbhl/bhl-us-data-sets/master/Flickr-Harvest/BHLFlickrDetails2.zip",
    "https://raw.githubusercontent.com/gbhl/bhl-us-data-sets/master/Flickr-Harvest/BHLFlickrDetails3.zip",
    "https://raw.githubusercontent.com/gbhl/bhl-us-data-sets/master/Flickr-Harvest/BHLFlickrDetails4.zip"
]

# Download each zip file and save it to disk
for url in zip_urls:
    filename = Path(url).name  # Extract file name from URL
    zip_path = zip_dir / filename
    print(f"Downloading {url} to {zip_path} ...")
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to download {url}")
        continue
    zip_path.write_bytes(response.content)
    print(f"Saved {zip_path}")

# Extract the downloaded zip files into separate folders under 'extracted'
for zip_file in zip_dir.glob("*.zip"):
    print(f"Extracting {zip_file}...")
    with zipfile.ZipFile(zip_file, "r") as z:
        # Create a subfolder named after the zip file (without extension)
        extract_subdir = extracted_dir / zip_file.stem
        extract_subdir.mkdir(exist_ok=True)
        z.extractall(extract_subdir)
        print(f"Extracted to {extract_subdir}")

# Function to read file content with fallback encodings
def read_file_with_encodings(file_path, encodings=("utf-8", "utf-16", "latin-1")):
    raw_bytes = file_path.read_bytes()
    for enc in encodings:
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(f"Could not decode {file_path} with tried encodings.")

# Initialize a list to collect master records
master_rows = []

# Recursively search for all files in the extracted directory.
# We assume the files contain JSON data.
for file_path in extracted_dir.rglob("*"):
    if file_path.is_file():
        print(f"Processing {file_path}...")
        try:
            content = read_file_with_encodings(file_path)
        except Exception as e:
            print(f"Could not read {file_path}: {e}")
            continue

        # Try loading the file content as JSON.
        try:
            # Some files may be a single JSON array
            data = json.loads(content)
        except json.JSONDecodeError:
            # Otherwise, assume newline-delimited JSON records
            data = []
            for line in content.splitlines():
                line = line.strip()
                if line:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        # Process each JSON record if it contains a "Pages" list.
        for page in data.get("Pages", []):
                title = page.get("Title", "")
                title_id = page.get("TitleID", "")
                flickr_id = page.get("PhotoID", "")
                page_id = page.get("PageID", "")
                master_rows.append([title, title_id, flickr_id, page_id])

# Write out the master TSV file
output_file = tsv_dir / "master.tsv"
with output_file.open("w", newline='', encoding="utf-8") as tsvfile:
    writer = csv.writer(tsvfile, delimiter="\t")
    # Write header
    writer.writerow(["Title", "Title ID", "Flickr ID", "BHL Page ID"])
    # Write each record row
    for row in master_rows:
        writer.writerow(row)

print(f"Master TSV file '{output_file}' has been created with {len(master_rows)} records.")
