CATEGORY_RAW = "Category:A_monograph_of_the_Capitonidæ,_or_scansorial_barbets"
TEST = False
ALL_DRAWINGS = True
SET_PROMINENT = True

SKIP_PUBLISHED_IN = False
SKIP_DATES = True

SKIP_EXISTING_INSTANCE_OF = True
PHOTOGRAPHS_ONLY = False
ADD_EMPTY_IF_SPONSOR_MISSING = True


ILLUSTRATOR = "Q1335286"
PAINTER = ""
ENGRAVER = ""
LITHOGRAPHER = ""
REF_URL_FOR_AUTHORS = ""

COMMONS_API_ENDPOINT = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
BHL_BASE_URL = "https://www.biodiversitylibrary.org"

CATEGORY_NAME = CATEGORY_RAW.replace("_", " ").replace("Category:", "").strip()
