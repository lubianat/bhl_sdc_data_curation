from flask import Flask, request, render_template_string
from login import BHL_API_KEY
from wdcuration import lookup_id, render_qs_url  # for looking up author QIDs
import requests
import re

app = Flask(__name__)

# BHL API URL Template
BHL_TITLE_METADATA_URL = "https://www.biodiversitylibrary.org/api3?op=GetTitleMetadata&id={title_id}&format=json&items=true&apikey=" + BHL_API_KEY

# HTML Template (basic)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>BHL Title QuickStatements Generator</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        input, button { font-size: 16px; padding: 5px; margin: 5px; }
        textarea { width: 100%; height: 150px; font-size: 14px; }
        .container { max-width: 600px; margin: auto; }
        .info { margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>BHL Title QuickStatements Generator</h2>
        <p>Enter a BHL Title ID or DOI (e.g., http://dx.doi.org/10.5962/bhl.title.102740).</p>
        <form method="get">
            <input type="text" name="bhl" placeholder="Enter BHL Title ID or DOI" required>
            <button type="submit">Generate QuickStatements</button>
        </form>
        {% if title_id %}
            <h3>Results for BHL Title ID: {{ title_id }}</h3>
            {% if title_data %}
                <h4>Title: {{ title_data.FullTitle }}</h4>
                <h4>QuickStatements:</h4>
                <textarea readonly>{{ quickstatements }}</textarea>
                <br>
                
                <a href="{{ qs_url }}" target="_blank"><button>Open QuickStatements URL</button></a>
            {% else %}
                <p>No title metadata found.</p>
            {% endif %}
        {% endif %}
    </div>
</body>
</html>
"""

def parse_bhl_title_id(input_str):
    """Extract the numeric BHL Title ID from the input.
    It accepts either a DOI (e.g. http://dx.doi.org/10.5962/bhl.title.102740)
    or a plain numeric ID."""
    # Look for a pattern like 'bhl.title.<digits>'
    match = re.search(r"bhl\.title\.(\d+)", input_str)
    if match:
        return match.group(1)
    # If not found, assume the input is the ID itself (all digits)
    if input_str.isdigit():
        return input_str
    # Otherwise, try to get trailing digits
    match = re.search(r"(\d+)$", input_str)
    if match:
        return match.group(1)
    return None

def get_bhl_title_metadata(title_id):
    """Fetch title metadata for a given BHL Title ID."""
    request_url = BHL_TITLE_METADATA_URL.format(title_id=title_id)
    response = requests.get(request_url)
    if response.status_code != 200:
        return None
    data = response.json()
    if data.get("Status") != "ok" or not data.get("Result"):
        return None
    return data["Result"][0]

def generate_title_quickstatements(title_data):
    """Generate QuickStatements commands for creating a Wikidata page for the title."""
    commands = []
    full_title = title_data.get("FullTitle", "Unknown Title")
    bhl_title_id = title_data.get("TitleID", "")
    title_url = f"https://www.biodiversitylibrary.org/bibliography/{bhl_title_id}"
    
    # Create the new Wikidata item for the title
    commands.append("CREATE")
    commands.append(f'LAST|Lmul|"{full_title}"')
    commands.append(f'LAST|Den|"title in the Biodiversity Heritage Library collection"')

    # Set instance of bibliographic work (Q47461344); adjust if needed
    commands.append("LAST|P31|Q47461344")
    # Add the BHL Title ID (property P4327)
    commands.append(f'LAST|P4327|"{bhl_title_id}"')
    # Add the reference URL
    commands.append(f'LAST|P953|"{title_url}"')
    
    for identifier in title_data.get("Identifiers", []):
        if identifier["IdentifierName"] == "DOI":
            commands.append(f'LAST|P356|"{identifier["IdentifierValue"].upper()}"|S854|"https://www.biodiversitylibrary.org/bibliography/{bhl_title_id}"')
        elif identifier["IdentifierName"] == "ISSN":
            commands.append(f'LAST|P236|"{identifier["IdentifierValue"].upper()}"|S854|"https://www.biodiversitylibrary.org/bibliography/{bhl_title_id}"')
        elif identifier["IdentifierName"] == "OCLC":
            commands.append(f'LAST|P243|"{identifier["IdentifierValue"].upper()}"|S854|"https://www.biodiversitylibrary.org/bibliography/{bhl_title_id}"')
    # Add authors as creators if available
    for author in title_data.get("Authors", []):
        author_qid = lookup_id(id=author["AuthorID"], property="P4081")
        author_name = author["Name"]
        if author_qid:
            commands.append(f'LAST|P50|{author_qid}|S854|"https://www.biodiversitylibrary.org/bibliography/{bhl_title_id}"|S1932|"{author_name}"\n')
        else:
            print(f"QID NOT FOUND FOR author: {author}")
            commands.append(f'LAST|P2093|"{author_name}"|S854|"https://www.biodiversitylibrary.org/bibliography/{bhl_title_id}"')
    
    return "\n\n".join(commands)

@app.route("/", methods=["GET"])
def index():
    bhl_input = request.args.get("bhl", "").strip()
    if not bhl_input:
        return render_template_string(HTML_TEMPLATE)
    
    title_id = parse_bhl_title_id(bhl_input)
    if not title_id:
        return render_template_string(HTML_TEMPLATE, title_id="Invalid input", title_data=None,
                                      quickstatements="Could not extract a valid BHL Title ID.")
    
    title_data = get_bhl_title_metadata(title_id)
    if not title_data:
        return render_template_string(HTML_TEMPLATE, title_id=title_id, title_data=None,
                                      quickstatements="No metadata found for this BHL Title ID.")
    
    quickstatements = generate_title_quickstatements(title_data)
    qs_url = render_qs_url(quickstatements)
    return render_template_string(HTML_TEMPLATE, title_id=title_id, title_data=title_data, quickstatements=quickstatements, qs_url=qs_url)

if __name__ == "__main__":
    app.run(debug=True)
