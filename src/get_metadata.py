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

 #Impleement get_bhl_title_data with caching
def get_bhl_title_data(biblio_id):
    global API_CACHE
    if biblio_id in API_CACHE:
        return API_CACHE["biblio_ids"][biblio_id]
    api_url = "https://www.biodiversitylibrary.org/api3"
    params = {
        "op": "GetTitleMetadata",
        "id": biblio_id,
        "format": "json",
        "apikey": BHL_API_KEY
    }
    response = requests.get(api_url, params=params)
    if response.status_code == 200:
        title_data = response.json().get("Result", {})
    else:
        print(f"Failed to fetch BHL title metadata for Title ID {biblio_id}. HTTP Status Code: {response.status_code}")
        title_data = {}
    return title_data

def get_bhl_item_data(item_id):
    global API_CACHE
    if item_id in API_CACHE:
        return API_CACHE["item_ids"][item_id]
    api_url = "https://www.biodiversitylibrary.org/api3"
    params = {
        "op": "GetItemMetadata",
        "id": item_id,
        "idtype": "bhl",
        "format": "json",
        "apikey": BHL_API_KEY
    }
    response = requests.get(api_url, params=params)
    if response.status_code == 200:
        item_data = response.json().get("Result", {})
    else:
        print(f"Failed to fetch BHL item metadata for Item ID {item_id}. HTTP Status Code: {response.status_code}")
        item_data = {}
    return item_data

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
    rows = []
    processed_counter = 0
    processed_creators = False

    for file in tqdm(files):
        if TEST and processed_counter >= 3:
            break
        processed_counter+=1
        wikitext = get_commons_wikitext(file)
        
        bhl_page_id = ""

        # Check if the file contains the BHL template.
        if "{{BHL" in wikitext:
                    
            # Parse the BHL template from the wikitext.
            bhl_page_id = find_page_id_in_bhl_template(wikitext)
        else:

            # If not, but it appears to be an IA source and the flag is set, try to infer.
            if "BHL Consortium" in wikitext and INFER_FROM_INTERNET_ARCHIVE:
                m = re.search(r'https://archive\.org/stream/([^#]+)#page/n(\d+)', wikitext)
                if m:
                    ia_url = m.group(0)  # The full URL.
                    inferred_page_id, inferred_item_id, inferred_biblio_id = infer_bhl_page_id_from_ia_url(ia_url, INTERNET_ARCHIVE_OFFSET)
                    if inferred_page_id:
                        bhl_page_id = str(inferred_page_id)
                    else:
                        bhl_page_id = ""
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
                    bhl_page_id = next(key for key, value in BHL_TO_FLICKR_DICT.items() if value == flickr_id)
            else:
                # Search for either a BHL page link or pageimage link in the full text
                # Add all match groups to bhl_ids
                bhl_ids = re.findall(r'https://www\.biodiversitylibrary\.org/page/(\d+)', wikitext)
                bhl_ids += re.findall(r'https://www\.biodiversitylibrary\.org/pageimage/(\d+)', wikitext)
                if len(set(bhl_ids)) == 1:
                    bhl_page_id = bhl_ids[0]
                else:
                    continue

        if not bhl_page_id:
            continue
        bhl_page_id = str(bhl_page_id)
        # Overwrite flickr_id if we have a mapping.
        if bhl_page_id in BHL_TO_FLICKR_DICT.keys():
            flickr_id = BHL_TO_FLICKR_DICT[bhl_page_id]
        else:
            flickr_id = ""
        page_data = get_bhl_page_data(bhl_page_id)
        if not page_data:
            continue
            
        item_id = page_data[0].get("ItemID")
        
        # Print URL and prompt for additional metadata on the first encounter.
        item_data = get_bhl_item_data(item_id)
        biblio_id = item_data[0].get("TitleID")
        biblio_data = get_bhl_title_data(biblio_id)
        wiki_ids_counter = 0
        for identifiers in biblio_data[0].get("Identifiers", []):
            if identifiers.get("IdentifierName") == "Wikidata":
                publication_qid = identifiers.get("IdentifierValue")
                wiki_ids_counter += 1
        if wiki_ids_counter != 1:
            # Throw exception if there are no Wikidata IDs or more than one. 
            # This is a critical error that needs to be resolved manually.
            raise Exception(f"Unexpected number of Wikidata IDs ({wiki_ids_counter}) for BHL Title ID {biblio_id}.")            
                
        page_types = "; ".join([a.get("PageTypeName", "") for a in page_data[0].get("PageTypes", [])])
        names = page_data[0].get("Names", [])
        pagenumbers = [f"{a['Prefix']} {a['Number']}" for a in page_data[0].get("PageNumbers", [])]
        
        holding_institution = item_data[0].get("HoldingInstitution", "")
        sponsor = item_data[0].get("Sponsor", "")
        item_publication_date = biblio_data[0].get("PublicationDate", "")
        copyright_status = item_data[0].get("CopyrightStatus")
        
        if app_mode:
            illustrator = ILLUSTRATOR
            painter = PAINTER
            engraver = ENGRAVER
            lithographer = LITHOGRAPHER
            ref_url_for_authors = REF_URL_FOR_AUTHORS

        else:
            if not processed_creators:
                illustrator = ILLUSTRATOR if ILLUSTRATOR != "" else input("Enter the Illustrator QID: ").strip()
                painter = PAINTER if PAINTER != "" else input("Enter the Painter QID: ").strip()
                engraver = ENGRAVER if ENGRAVER != "" else input("Enter the Engraver QID: ").strip()
                lithographer = LITHOGRAPHER if LITHOGRAPHER != "" else input("Enter the Lithographer QID: ").strip()
                ref_url_for_authors = REF_URL_FOR_AUTHORS if REF_URL_FOR_AUTHORS != "" else input("Enter the Ref URL for the authors: ").strip()
                processed_creators = True


        flickr_tags = get_flickr_tags(flickr_id)
            # Create the metadata row. For files with the BHL template, we include names; otherwise, leave blank.
        row = {
            "File": file or "",
            "BHL Page ID": bhl_page_id or "",
            "Page Types": page_types or "",
            "Published In QID": publication_qid or "",
            "Collection": holding_institution or "",
            "Sponsor": sponsor or "",
            "Bibliography ID": biblio_id or "",
            "Illustrator": illustrator or "",
            "Engraver": engraver or "",
            "Lithographer": lithographer or "",
            "Painter": painter or "",
            "Ref URL for Authors": ref_url_for_authors or "",
            "Item Publication Date": item_publication_date or "",
            "Item ID": item_id or "",
            "Flickr ID": flickr_id or "",
            "Flickr Tags": flickr_tags or ""
        }
        rows.append(row)
    
    return rows

def get_bhl_page_data(bhl_page_id):
    api_url = "https://www.biodiversitylibrary.org/api3"
    params = {
            "op": "GetPageMetadata",
            "pageid": bhl_page_id,
            "ocr": "false",
            "names": "true",
            "format": "json",
            "apikey": BHL_API_KEY
            }
    response = requests.get(api_url, params=params)
    if response.status_code == 200:
        page_data = response.json().get("Result", {})
    else:
        print(f"Failed to fetch BHL page metadata for Page ID {bhl_page_id}. HTTP Status Code: {response.status_code}")
        page_data = {}
    return page_data
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


def find_page_id_in_bhl_template(wikitext):
    if not wikitext:
        return {"pageid": ""}
    m = re.search(r'\|\s*pageid\s*=\s*(\d+)', wikitext)
    if m:
        return  m.group(1).strip()
    return ""

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
