import requests
from wdcuration import lookup_id
import random

COMMONS_API_ENDPOINT = "https://commons.wikimedia.org/w/api.php"


def generate_custom_edit_summary(test_edit=False):
    global SKIP_CREATOR
    # As per https://www.wikidata.org/wiki/Wikidata:Edit_groups/Adding_a_tool
    random_hex = f"{random.randrange(0, 2**48):x}"
    editgroup_snippet = f"([[:toolforge:editgroups-commons/b/CB/{random_hex}|details]])"
    if test_edit:
        return f"SDC import (BHL Model v0.1.6 - tests)"
    else:
        return f"SDC import (BHL Model v0.1.6) {editgroup_snippet}"


def get_files_in_category(category_name, include_subcategories=False):
    files = []
    # Get files in the current category
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category_name}",
        "cmtype": "file",
        "cmlimit": "max",
        "format": "json",
    }
    try:
        r = requests.get(COMMONS_API_ENDPOINT, params=params)
        data = r.json()
        files += [
            member["title"].replace("File:", "")
            for member in data.get("query", {}).get("categorymembers", [])
        ]
    except Exception:
        pass

    # If requested, get files from subcategories as well
    if include_subcategories:
        subcat_params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category_name}",
            "cmtype": "subcat",
            "cmlimit": "max",
            "format": "json",
        }
        try:
            r = requests.get(COMMONS_API_ENDPOINT, params=subcat_params)
            data = r.json()
            subcategories = data.get("query", {}).get("categorymembers", [])
            for subcat in subcategories:
                # Remove the "Category:" prefix to get the clean category name
                subcat_name = subcat["title"].replace("Category:", "")
                # Recursively get files from this subcategory (including its subcategories)
                files.extend(
                    get_files_in_category(subcat_name, include_subcategories=True)
                )
        except Exception:
            pass

    return files


def get_commons_wikitext(filename):
    params = {
        "action": "query",
        "prop": "revisions",
        "titles": "File:" + filename,
        "rvslots": "*",
        "rvprop": "content",
        "formatversion": "2",
        "format": "json",
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


def get_media_info_id(file_name):
    API_URL = "https://commons.wikimedia.org/w/api.php"
    if "File:" in file_name:
        file_name = file_name.replace("File:", "")
    params = {
        "action": "query",
        "titles": f"File:{file_name}",
        "prop": "info",
        "format": "json",
    }
    try:
        response = requests.get(API_URL, params=params)
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return "Error: No page data found for the file."
        page = next(iter(pages.values()))
        if "pageid" in page:
            media_info_id = f"M{page['pageid']}"
            return media_info_id
        else:
            return "Error: MediaInfo ID could not be found for the file."
    except requests.RequestException as e:
        return f"Error: API request failed. {e}"


def get_wikidata_qid_from_gbif(name):
    # GBIF species match endpoint
    url = "http://api.gbif.org/v1/species/match"
    params = {"name": name}

    response = requests.get(url, params=params)
    if response.status_code != 200:
        print("Error: Unable to reach GBIF API")
        return

    data = response.json()
    gbif_id = data.get("speciesKey")
    qid = lookup_id(gbif_id, property="P846")
    # If GBIF identifies the name as a synonym, it returns "synonym": true
    if data.get("synonym", False):
        current_species_name = data.get("species")
        if current_species_name:
            print(
                f"'{name}' is a synonym. The current accepted name is: {current_species_name}"
            )
        return qid
    if not qid:
        print(f"Error: Unable to find Wikidata QID for '{name}'")
        return ""
    return qid
