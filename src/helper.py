import requests
COMMONS_API_ENDPOINT = "https://commons.wikimedia.org/w/api.php"

###### Commons query functions  ###### 

def get_files_in_category(category_name, include_subcategories=False):
    files = []
    # Get files in the current category
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
        files += [member["title"].replace("File:", "") 
                  for member in data.get("query", {}).get("categorymembers", [])]
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
            "format": "json"
        }
        try:
            r = requests.get(COMMONS_API_ENDPOINT, params=subcat_params)
            data = r.json()
            subcategories = data.get("query", {}).get("categorymembers", [])
            for subcat in subcategories:
                # Remove the "Category:" prefix to get the clean category name
                subcat_name = subcat["title"].replace("Category:", "")
                # Recursively get files from this subcategory (including its subcategories)
                files.extend(get_files_in_category(subcat_name, include_subcategories=True))
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
