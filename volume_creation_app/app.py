from flask import Flask, request, render_template_string
from login import BHL_API_KEY
from wdcuration import get_statement_values, today_in_quickstatements, lookup_id

import requests

app = Flask(__name__)


# Wikidata Base URL
WIKIDATA_URL = "https://www.wikidata.org/wiki/"

# BHL API URL Template
BHL_TITLE_METADATA_URL = "https://www.biodiversitylibrary.org/api3?op=GetTitleMetadata&id={title_id}&format=json&items=true&apikey=" + BHL_API_KEY

# HTML Template (very basic)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>BHL Volume Fetcher</title>
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
        <h2>BHL Volume Fetcher</h2>
        <p>Enter a Wikidata QID to fetch BHL volumes and generate QuickStatements.</p>
        <form method="get">
            <input type="text" name="qid" placeholder="Enter Wikidata QID (e.g., Q51488695)" required>
            <button type="submit">Fetch Volumes</button>
        </form>
        {% if qid %}
            <h3>Results for <a href="{{ wikidata_url }}" target="_blank">{{ qid }}</a></h3>
            {% if volumes %}
                <h4>Found Volumes:</h4>
                <ul>
                    {% for vol in volumes %}
                        <li>
                            <strong>Volume {{ vol['number'] }}</strong> ({{ vol['year'] }}) - 
                            <a href="{{ vol['bhl_url'] }}" target="_blank">BHL Link</a>
                        </li>
                    {% endfor %}
                </ul>
                <h4>QuickStatements:</h4>
                <textarea readonly>{{ quickstatements }}</textarea>
            {% else %}
                <p>No volumes found.</p>
            {% endif %}
        {% endif %}
    </div>
</body>
</html>
"""

def get_bhl_volumes(title_id):
    """Fetch volumes for a given BHL Title ID."""
    request_url = BHL_TITLE_METADATA_URL.format(title_id=title_id)
    response = requests.get(request_url)
    if response.status_code != 200:
        return []

    data = response.json()
    if data["Status"] != "ok":
        return []

    volumes = []
    bhl_author_qids = []
    for author in data["Result"][0].get("Authors", []):
        qid = lookup_id(id=author["AuthorID"],property="P4081")
        if qid:
            bhl_author_qids.append(qid)
        else:
            print(f"QID NOT FOUND FOR {author}")
            

    for item in data["Result"][0].get("Items", []):
        volume = {
            "number": item.get("Volume", "Unknown"),
            "full_title": data["Result"][0]["FullTitle"],
            "year": item.get("Year", "Unknown"),
            "bhl_url": f"https://www.biodiversitylibrary.org/item/{item['ItemID']}",
            "bhl_title_id":title_id,
            "item_id": item['ItemID'],
            "bhl_author_qids": bhl_author_qids
        }
        volumes.append(volume)
    
    return volumes

def generate_quickstatements(qid, volumes):
    """Generate QuickStatements commands for adding volumes to Wikidata."""
    commands = []

    # TODO add parsing of authors
    for vol in volumes:
        commands.append(f"""
CREATE
LAST|Lmul|"{vol['full_title']}, {vol['number']}"
LAST|P31|Q3331189
LAST|P361|{qid}
LAST|P478|"{vol['number']}"|S854|"https://www.biodiversitylibrary.org/bibliography/{vol['bhl_title_id']}"
LAST|P577|+{vol['year']}-00-00T00:00:00Z/9|S854|"https://www.biodiversitylibrary.org/bibliography/{vol['bhl_title_id']}"
LAST|P11959|"{vol['item_id']}"
LAST|P953|"{vol['bhl_url']}" """.strip())

        for author_qid in vol["bhl_author_qids"]:
             commands.append(f"LAST|P50|{author_qid}|S854|\"https://www.biodiversitylibrary.org/bibliography/{vol['bhl_title_id']}\"")
    
        commands.append(f"""
{qid}|P527|LAST
            """.strip())
    return "\n\n".join(commands)

@app.route("/")
def index():
    qid = request.args.get("qid").strip()
    if not qid:
        return render_template_string(HTML_TEMPLATE)

    # Extract the BHL Title ID from the Wikidata QID
    bhl_title_ids = get_statement_values(qid, property="P4327")

    if len(bhl_title_ids) == 1:
        bhl_title_id = bhl_title_ids[0]
    else:
        bhl_title_id = input("Enter the BHL Title ID.")
    volumes = get_bhl_volumes(bhl_title_id)
    quickstatements = generate_quickstatements(qid, volumes) if volumes else ""

    return render_template_string(HTML_TEMPLATE, qid=qid, wikidata_url=WIKIDATA_URL + qid, volumes=volumes, quickstatements=quickstatements)

if __name__ == "__main__":
    app.run(debug=True)
