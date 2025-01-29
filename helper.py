import random
import requests


def generate_custom_edit_summary(test_edit=False):
    # As per https://www.wikidata.org/wiki/Wikidata:Edit_groups/Adding_a_tool
    random_hex = f"{random.randrange(0, 2**48):x}"
    editgroup_snippet = f"([[:toolforge:editgroups-commons/b/CB/{random_hex}|details]])"
    if test_edit:
         return f"SDC import (BHL Model v0.1.1, manual curation - tests)"
    else:
        return f"SDC import (BHL Model v0.1.1, manual curation) {editgroup_snippet}"
    
def get_media_info_id(file_name):
    API_URL = "https://commons.wikimedia.org/w/api.php"
    if "File:" in file_name:
        file_name = file_name.replace("File:", "")
    params = {
        "action": "query",
        "titles": f"File:{file_name}",
        "prop": "info",
        "format": "json"
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
