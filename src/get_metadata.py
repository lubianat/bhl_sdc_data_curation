import requests
import re
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm
import requests
from login import * 
from config import *

def get_flickr_tags(photo_id):
    API_ENDPOINT = "https://www.flickr.com/services/rest/"
    params = {
        "method": "flickr.tags.getListPhoto",
        "api_key": FLICKR_API_KEY,
        "photo_id": photo_id,
        "format": "json",
        "nojsoncallback": 1  # Prevent JSONP callback, get plain JSON
    }
    response = requests.get(API_ENDPOINT, params=params)
    tag_raw_content = []
    if response.status_code == 200:
        data = response.json()
        if data.get("stat") == "ok":
            print("Tags for Photo ID", photo_id)
            tags = data["photo"]["tags"]["tag"]
            for tag in tags:
                print(f"- {tag['raw']}")
                tag_raw_content.append(tag['raw'])
        else:
            print("Error:", data.get("message"))
    else:
        print("Failed to fetch tags. HTTP Status Code:", response.status_code)
    return tag_raw_content

def get_files_in_category(category_name):
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category_name}",
        "cmtype": "file",
        "cmlimit": "max",
        "format": "json"
    }
    try:
        r = requests.get(COMMONS_API_ENDPOINT, params=params)
        data = r.json()
        files = data.get("query", {}).get("categorymembers", [])
        return [file["title"].replace("File:", "") for file in files]
    except Exception:
        return []

def get_commons_wikitext(filename):
    params = {
        "action": "query",
        "prop": "revisions",
        "titles": "File:" + filename,
        "rvslots": "*",
        "rvprop": "content",
        "formatversion": "2",
        "format": "json"
    }
    try:
        r = requests.get(COMMONS_API_ENDPOINT, params=params)
        data = r.json()
        pages = data.get("query", {}).get("pages", [])
        if not pages or "missing" in pages[0]:
            return ""
        return pages[0]["revisions"][0]["slots"]["main"]["content"]
    except Exception:
        return ""

def parse_bhl_template(wikitext):
    if not wikitext:
        return {field: "" for field in ["pageid", "titleid", "pagetypes", "date", "author", "names", "source"]}
    m = re.search(r'(?s)\{\{BHL\s*\|.*?\}\}', wikitext)
    if not m:
        return {field: "" for field in ["pageid", "titleid", "pagetypes", "date", "author", "names", "source"]}
    bhl_block = m.group(0)
    field_names = ["pageid", "titleid", "pagetypes", "date", "author", "names", "source"]
    results = {}
    for field in field_names:
        regex = r"\|\s*{}\s*=\s*(.*?)\n".format(field)
        fm = re.search(regex, bhl_block)
        if fm:
            value = fm.group(1).strip()
            value = re.sub(r"\}\}.*", "", value).strip()
            if field == "names":
                # Example: | names = NameFound:Dicholophus cristatus NameConfirmed:Dicholophus cristatus  
                # Regex to get the scientific name after NameFound)
                try:
                    value = re.search(r"NameFound:([A-Za-z ]+)NameConfirmed", value).group(1)
                except AttributeError:
                    try:
                        value = re.search(r"NameFound:([A-Za-z ]+)", value).group(1)
                    except AttributeError:
                        value = value
            results[field] = value
        else:
            results[field] = ""
    return results

def find_publication_from_category(category_name):
    query = f"""
    SELECT ?item ?itemLabel ?publicationDate ?bhl_bib_id
    WHERE
    {{
      ?item wdt:P373 "{category_name}" .
      ?item wdt:P4327 ?bhl_bib_id .
      OPTIONAL {{ ?item wdt:P577 ?publicationDate. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    try:
        r = requests.get(
            WIKIDATA_SPARQL_ENDPOINT,
            params={'query': query, 'format': 'json'}
        )
        data = r.json()
        results = data.get("results", {}).get("bindings", [])
        if len(results) == 0 :
            print(f"No BHL IDs found for category {category_name}.")
            return "", "", ""
        if results:
            qid = results[0].get("item", {}).get("value", "").split("/")[-1]
            label = results[0].get("itemLabel", {}).get("value", "")
            publication_date = results[0].get("publicationDate", {}).get("value", "").split("T")[0]
            return qid, label, publication_date
    except Exception:
        pass
    return "", "", ""

def scrape_bhl_details(bhl_url):
    try:
        r = requests.get(bhl_url)
        soup = BeautifulSoup(r.text, "html.parser")
        holding_institution = soup.find("h5", text="Holding Institution:").find_next("p").text.strip()
        sponsor = soup.find("h5", text="Sponsor:").find_next("p").text.strip()
        return holding_institution, sponsor
    except Exception:
        return "", ""

def generate_data(category_name):
    files = get_files_in_category(category_name)
    publication_qid, publication_title, inception_date = find_publication_from_category(category_name)
    rows = []
    
    url_printed = False
    for file in tqdm(files):
        wikitext = get_commons_wikitext(file)
        # SKIP non-BHL templated files
        if "{{BHL" not in wikitext:
            continue
        bhl_data = parse_bhl_template(wikitext)
        instance_of = bhl_data["pagetypes"]
        biblio_id = bhl_data["titleid"]
        # | source = https://www.flickr.com/photos/biodivlibrary/20552772278
        flickr_id = bhl_data["source"].split("/")[-1] if bhl_data["source"] else ""
        if not url_printed:
            bhl_url = f"{BHL_BASE_URL}/bibliography/{biblio_id}"
            print(f"Visit the BHL page for this category: {bhl_url}")
            collection, sponsor = scrape_bhl_details(bhl_url)
            print(f"Detected Collection: {collection}")
            print(f"Detected Sponsor: {sponsor}")
            if not collection:
                collection = input("Enter the Collection (if not auto-detected): ").strip()
            if not sponsor:
                sponsor = input("Enter the Sponsor (if not auto-detected): ").strip()
            if ILLUSTRATOR != "":
                illustrator = ILLUSTRATOR
            else:
                illustrator = input("Enter the Illustrator QID: ").strip()
            if ENGRAVER != "":
                engraver = ENGRAVER
            else:
                engraver = input("Enter the Engraver QID: ").strip()
            if LITHOGRAPHER != "":
                lithographer = LITHOGRAPHER
            else:
                lithographer = input("Enter the Lithographer QID: ").strip()
            if REF_URL_FOR_AUTHORS != "":
                ref_url_for_authors = REF_URL_FOR_AUTHORS
            else: 
                ref_url_for_authors = input("Enter the Ref URL for the authors: ").strip()
            url_printed = True

        flickr_tags = get_flickr_tags(flickr_id)
        row = {
            "File": file or "",
            "BHL Page ID": bhl_data["pageid"] or "",
            "Instance of": instance_of or "",
            "Published In": publication_title or "",
            "Published In QID": publication_qid or "",
            "Collection": collection or "",
            "Sponsor": sponsor or "",
            "Bibliography ID": biblio_id or "",
            "Illustrator": illustrator or "",
            "Engraver": engraver or "",
            "Lithographer": lithographer or "",
            "Ref URL for Authors": ref_url_for_authors or "",
            "Inception": inception_date or "",
            "Names": bhl_data["names"] or "",
            "Flickr ID": flickr_id or "",
            "Flickr Tags": flickr_tags or ""
        }
        rows.append(row)
    
    return rows

# Main logic
data = generate_data(CATEGORY_NAME)
HERE = Path(__file__).parent
output_path = HERE / "data"
output_path.mkdir(parents=True, exist_ok=True)
output_file = output_path / f"{CATEGORY_NAME.replace(' ', '_')}.tsv"

df = pd.DataFrame(data)
df.to_csv(output_file, sep="\t", index=False)

print(f"Data written to: {output_file}")
