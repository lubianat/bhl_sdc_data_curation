import requests


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
