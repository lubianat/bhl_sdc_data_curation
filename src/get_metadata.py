import re
import requests
import json
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm
from login import *
import re
import requests
import json
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm
from login import *


# Directories for data and dictionaries
HERE = Path(__file__).parent
DATA = HERE / "data"
DICTS = HERE / "dicts"
API_CACHE = {}

# Load the dictionary mapping BHL page IDs to Flickr IDs
BHL_TO_FLICKR_DICT = json.loads(DICTS.joinpath("bhl_flickr_dict.json").read_text())
def load_config():
    with open(HERE / "config.json", "r") as config_file:
        return json.load(config_file)

config = load_config()
CATEGORY_RAW = config["CATEGORY_RAW"]
TEST = config["TEST"]
ALL_DRAWINGS = config["ALL_DRAWINGS"]
SKIP_CREATOR = config["SKIP_CREATOR"]
INFER_BHL_PAGE_FROM_FLICKR_ID = config["INFER_BHL_PAGE_FROM_FLICKR_ID"]
INFER_FROM_INTERNET_ARCHIVE = config["INFER_FROM_INTERNET_ARCHIVE"]
INTERNET_ARCHIVE_OFFSET = config["INTERNET_ARCHIVE_OFFSET"]
PHOTOGRAPHS_ONLY = config["PHOTOGRAPHS_ONLY"]
ILLUSTRATOR = config["ILLUSTRATOR"]
PAINTER = config["PAINTER"]
ENGRAVER = config["ENGRAVER"]
LITHOGRAPHER = config["LITHOGRAPHER"]
REF_URL_FOR_AUTHORS = config["REF_URL_FOR_AUTHORS"]
COMMONS_API_ENDPOINT = config["COMMONS_API_ENDPOINT"]
WIKIDATA_SPARQL_ENDPOINT = config["WIKIDATA_SPARQL_ENDPOINT"]
BHL_BASE_URL = config["BHL_BASE_URL"]
SET_PROMINENT = config["SET_PROMINENT"]
SKIP_PUBLISHED_IN = config["SKIP_PUBLISHED_IN"]
SKIP_DATES = config["SKIP_DATES"]
ADD_EMPTY_IF_SPONSOR_MISSING = config["ADD_EMPTY_IF_SPONSOR_MISSING"]
SKIP_EXISTING_INSTANCE_OF = config["SKIP_EXISTING_INSTANCE_OF"]
TEST = config["TEST"]

CATEGORY_NAME = CATEGORY_RAW.replace("_", " ").replace("Category:", "").strip()

def generate_metadata(category_name, app_mode=False):
    global CATEGORY_NAME
    global CATEGORY_RAW
    global TEST
    global ALL_DRAWINGS
    global SKIP_CREATOR
    global INFER_BHL_PAGE_FROM_FLICKR_ID
    global INFER_FROM_INTERNET_ARCHIVE
    global INTERNET_ARCHIVE_OFFSET
    global PHOTOGRAPHS_ONLY
    global ILLUSTRATOR
    global PAINTER
    global ENGRAVER
    global LITHOGRAPHER
    global REF_URL_FOR_AUTHORS
    global COMMONS_API_ENDPOINT
    global WIKIDATA_SPARQL_ENDPOINT
    global BHL_BASE_URL
    global SET_PROMINENT
    global SKIP_PUBLISHED_IN
    global SKIP_DATES
    global ADD_EMPTY_IF_SPONSOR_MISSING
    global SKIP_EXISTING_INSTANCE_OF
    global TEST
    
        
    # Load configuration from config.json
    config = load_config()
    CATEGORY_RAW = config["CATEGORY_RAW"]
    TEST = config["TEST"]
    ALL_DRAWINGS = config["ALL_DRAWINGS"]
    SKIP_CREATOR = config["SKIP_CREATOR"]
    INFER_BHL_PAGE_FROM_FLICKR_ID = config["INFER_BHL_PAGE_FROM_FLICKR_ID"]
    INFER_FROM_INTERNET_ARCHIVE = config["INFER_FROM_INTERNET_ARCHIVE"]
    INTERNET_ARCHIVE_OFFSET = config["INTERNET_ARCHIVE_OFFSET"]
    PHOTOGRAPHS_ONLY = config["PHOTOGRAPHS_ONLY"]
    ILLUSTRATOR = config["ILLUSTRATOR"]
    PAINTER = config["PAINTER"]
    ENGRAVER = config["ENGRAVER"]
    LITHOGRAPHER = config["LITHOGRAPHER"]
    REF_URL_FOR_AUTHORS = config["REF_URL_FOR_AUTHORS"]
    COMMONS_API_ENDPOINT = config["COMMONS_API_ENDPOINT"]
    WIKIDATA_SPARQL_ENDPOINT = config["WIKIDATA_SPARQL_ENDPOINT"]
    BHL_BASE_URL = config["BHL_BASE_URL"]
    SET_PROMINENT = config["SET_PROMINENT"]
    SKIP_PUBLISHED_IN = config["SKIP_PUBLISHED_IN"]
    SKIP_DATES = config["SKIP_DATES"]
    ADD_EMPTY_IF_SPONSOR_MISSING = config["ADD_EMPTY_IF_SPONSOR_MISSING"]
    SKIP_EXISTING_INSTANCE_OF = config["SKIP_EXISTING_INSTANCE_OF"]
    TEST = config["TEST"]

    CATEGORY_NAME = CATEGORY_RAW.replace("_", " ").replace("Category:", "").strip()

    files = get_files_in_category(category_name)
    publication_qid, publication_title, inception_date = find_publication_from_category(category_name)
    rows = []
    inferred_collection = False
    processed_counter = 0
    processed_creators = False

    for file in tqdm(files):
        if TEST and processed_counter >= 3:
            break
        processed_counter+=1
        wikitext = get_commons_wikitext(file)
        
        # Initialize variables in case they are not set later.
        bhl_page_id = ""
        biblio_id = ""
        instance_of = ""
        flickr_id = ""
        names = ""

        # Check if the file contains the BHL template.
        if "{{BHL" not in wikitext:
            # If not, but it appears to be an IA source and the flag is set, try to infer.
            if "BHL Consortium" in wikitext and INFER_FROM_INTERNET_ARCHIVE:
                m = re.search(r'https://archive\.org/stream/([^#]+)#page/n(\d+)', wikitext)
                if m:
                    ia_url = m.group(0)  # The full URL.
                    inferred_page_id, inferred_item_id, inferred_biblio_id = infer_bhl_page_id_from_ia_url(ia_url, INTERNET_ARCHIVE_OFFSET)
                    if inferred_page_id:
                        bhl_page_id = str(inferred_page_id)
                        biblio_id = str(inferred_biblio_id)
                    else:
                        bhl_page_id = ""
                        biblio_id = ""
                else:
                    continue  # If no IA URL can be extracted, skip this file.

            # If the file has a Flickr URL in the wikitext, extract the ID.
            elif "https://www.flickr.com/photos/biodivlibrary/" in wikitext and INFER_BHL_PAGE_FROM_FLICKR_ID:
                # If the file has a Flickr URL in the wikitext, extract the ID.
                m = re.search(r'https://www\.flickr\.com/photos/biodivlibrary/(\d+)', wikitext)
                if m:
                    flickr_id = m.group(1)
                    flickr_id = flickr_id.split("/")[0]  # Remove any additional URL components.
                
                # Check the reverse of the BHL_TO_FLICKR_DICT to see if we have a mapping.
                if flickr_id in BHL_TO_FLICKR_DICT.values():
                    biblio_id = find_publication_from_category(category_name, return_bib_id=True)

                    bhl_page_id = next(key for key, value in BHL_TO_FLICKR_DICT.items() if value == flickr_id)
            else:
                continue
        else:
            # Parse the BHL template from the wikitext.
            bhl_data = parse_bhl_template(wikitext)
            bhl_page_id = bhl_data.get("pageid", "")
            instance_of = bhl_data.get("pagetypes", "")
            biblio_id = bhl_data.get("titleid", "")
            flickr_id = bhl_data.get("source", "").split("/")[-1] if bhl_data.get("source") else ""
            names = bhl_data.get("names", "")

        # Overwrite flickr_id if we have a mapping.
        if bhl_page_id in BHL_TO_FLICKR_DICT:
            flickr_id = BHL_TO_FLICKR_DICT[bhl_page_id]

        # Print URL and prompt for additional metadata on the first encounter.
        if not inferred_collection:
            bhl_url = f"{BHL_BASE_URL}/bibliography/{biblio_id}"
            print(f"Visit the BHL page for this category: {bhl_url}")
            inferred_collection = True

            collection, sponsor = scrape_bhl_details(bhl_url)
            print(f"Detected Collection: {collection}")
            print(f"Detected Sponsor: {sponsor}")
        
        
    
        if not app_mode:

            if not collection:
                collection = input("Enter the Collection (if not auto-detected): ").strip()
            if not sponsor:
                sponsor = input("Enter the Sponsor (if not auto-detected): ").strip()
            if not processed_creators:
                illustrator = ILLUSTRATOR if ILLUSTRATOR != "" else input("Enter the Illustrator QID: ").strip()
                painter = PAINTER if PAINTER != "" else input("Enter the Painter QID: ").strip()
                engraver = ENGRAVER if ENGRAVER != "" else input("Enter the Engraver QID: ").strip()
                lithographer = LITHOGRAPHER if LITHOGRAPHER != "" else input("Enter the Lithographer QID: ").strip()
                ref_url_for_authors = REF_URL_FOR_AUTHORS if REF_URL_FOR_AUTHORS != "" else input("Enter the Ref URL for the authors: ").strip()
                processed_creators = True

        else:
        # In app mode, simply use the current config values (or set to empty/default)
    
            illustrator = ILLUSTRATOR
            painter = PAINTER
            engraver = ENGRAVER
            lithographer = LITHOGRAPHER
            ref_url_for_authors = REF_URL_FOR_AUTHORS

        flickr_tags = get_flickr_tags(flickr_id)
            # Create the metadata row. For files with the BHL template, we include names; otherwise, leave blank.
        row = {
            "File": file or "",
            "BHL Page ID": bhl_page_id or "",
            "Instance of": instance_of or "",
            "Published In": publication_title or "",
            "Published In QID": publication_qid or "",
            "Collection": collection or "",
            "Sponsor": sponsor or "",
            "Bibliography ID": biblio_id or "",
            "Illustrator": illustrator or "",
            "Engraver": engraver or "",
            "Lithographer": lithographer or "",
            "Painter": painter or "",
            "Ref URL for Authors": ref_url_for_authors or "",
            "Inception": inception_date or "",
            "Names": names if "{{BHL" in wikitext else "",
            "Flickr ID": flickr_id or "",
            "Flickr Tags": flickr_tags or ""
        }
        rows.append(row)
    
    return rows

def infer_bhl_page_id_from_ia_url(ia_url, offset=0, ):
    """
    Given an Internet Archive URL of a BHL item, extract the IA item identifier and page number,
    adjust the page number by the given offset, and then use the BHL API to fetch the corresponding
    BHL page ID, item ID, and bibliography ID.
    
    For example, from:
      https://archive.org/stream/monographofjacam00scla/monographofjacam00scla#page/n125/mode/1up
    it extracts:
      item_id = 'monographofjacam00scla'
      ia_page_number = 125
    and then calculates target_order = ia_page_number - offset.
    """
    # Cache to store API results (local to this call; consider a module-level cache for efficiency)    
    global API_CACHE
    # Extract the IA item identifier from the URL.
    m_item = re.search(r'/stream/([^/]+)/', ia_url)
    if not m_item:
        print("Unable to extract IA item identifier from URL.")
        return None, None, None
    item_id = m_item.group(1)
    
    # Extract the IA page number from the URL; pattern like "page/n125"
    m_page = re.search(r'page/n(\d+)', ia_url)
    if not m_page:
        print("Unable to extract IA page number from URL.")
        return None, None, None
    ia_page_number = int(m_page.group(1))
    
    # Adjust the page number by the offset to get the target digital order.
    target_order = ia_page_number - offset
    if target_order < 1:
        print("Calculated target order is less than 1.")
        return None, None, None

    # Check the cache for metadata
    if item_id in API_CACHE:
        data = API_CACHE[item_id]
    else:
        api_url = "https://www.biodiversitylibrary.org/api3"
        params = {
            "op": "GetItemMetadata",
            "id": item_id,
            "idtype": "ia",  # The id is an Internet Archive identifier.
            "pages": "t",    # Include page metadata.
            "format": "json",
            "apikey": BHL_API_KEY
        }
        
        response = requests.get(api_url, params=params)
        if response.status_code != 200:
            print("BHL API request failed with status code:", response.status_code)
            return None, None, None

        data = response.json()
        if data.get("Status") != "ok":
            print("BHL API returned an error:", data.get("ErrorMessage"))
            return None, None, None

        # Cache the result
        API_CACHE[item_id] = data

    # Get the list of pages from the API response.
    # The response's "Result" is assumed to be a list; we use the first element.
    result = data.get("Result", [])
    if not result:
        print("No result in BHL API response.")
        return None, None, None

    pages = result[0].get("Pages", [])
    if not pages:
        print("No page metadata found in BHL API response.")
        return None, None, None

    if target_order > len(pages):
        print(f"Target order {target_order} exceeds available pages ({len(pages)}).")
        return None, None, None

    # Pages are assumed to be in order; select the page at the adjusted (1-indexed) position.
    bhl_page_id = pages[target_order - 1].get("PageID")
    bhl_item_id = result[0].get("ItemID")
    bhl_biblio_id = result[0].get("TitleID")
    return bhl_page_id, bhl_item_id, bhl_biblio_id

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

def get_taxon_names_from_api(pageid, api_key=BHL_API_KEY):
    url = "https://www.biodiversitylibrary.org/api2/httpquery.ashx"
    params = {
        "op": "GetPageNames",
        "pageid": pageid,
        "apikey": api_key,
        "format": "json"
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return ""
    data = response.json()
    if data.get("Status") != "ok":
        return ""
    names_list = [a.get("NameFound", "") for a in data.get("Result", [])]
    # Remove empty 
    names = [a for a in names_list if a]
    # Extract the 'NameFound' field from each record and join with semicolons
    return "; ".join(names)

def parse_bhl_template(wikitext):
    # Define the fields we expect from the BHL template
    fields = ["pageid", "titleid", "pagetypes", "date", "author", "names", "source"]
    if not wikitext:
        return {field: "" for field in fields}
    m = re.search(r'(?s)\{\{BHL\s*\|.*?\}\}', wikitext)
    if not m:
        return {field: "" for field in fields}
    bhl_block = m.group(0)
    results = {}
    for field in fields:
        regex = r"\|\s*{}\s*=\s*(.*?)\n".format(field)
        fm = re.search(regex, bhl_block)
        if fm:
            value = fm.group(1).strip()
            # Remove any trailing template closing braces and following text
            value = re.sub(r"\}\}.*", "", value).strip()
            results[field] = value
        else:
            results[field] = ""
    # If a pageid was found, override the "names" field with taxon names from the API.
    pageid = results.get("pageid")
    if pageid:
        results["names"] = get_taxon_names_from_api(pageid)
    return results

def find_publication_from_category(category_name, return_bib_id=False):
    query = f"""
    SELECT ?item ?itemLabel ?publicationDate ?bhl_bib_id ?bhl_item_id
    WHERE
    {{
      ?item wdt:P373 "{category_name}" .
      {{?item wdt:P4327 ?bhl_bib_id .}}
      UNION
      {{?item wdt:P11959 ?bhl_item_id .}}
      OPTIONAL {{ ?item wdt:P577 ?publicationDate. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    print(query)
    try:
        r = requests.get(
            WIKIDATA_SPARQL_ENDPOINT,
            params={'query': query, 'format': 'json'}
        )
        data = r.json()
        results = data.get("results", {}).get("bindings", [])
        if len(results) == 0 :
            print(f"No BHL IDs found for category {category_name}.")
            check = input("Do you want to continue? (y/n): ")
            return "", "", ""
        if results:
            qid = results[0].get("item", {}).get("value", "").split("/")[-1]
            label = results[0].get("itemLabel", {}).get("value", "")
            publication_date = results[0].get("publicationDate", {}).get("value", "").split("T")[0]
            if return_bib_id:
                bhl_bib_id = results[0].get("bhl_bib_id", {}).get("value", "")
                return bhl_bib_id
            else:
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


# Main logic
if __name__ == "__main__":
    data = generate_metadata(CATEGORY_NAME)
    output_file = DATA / f"{CATEGORY_NAME.replace(' ', '_')}.tsv"
    df = pd.DataFrame(data)
    df.to_csv(output_file, sep="\t", index=False)
    print(f"Data written to: {output_file}")
