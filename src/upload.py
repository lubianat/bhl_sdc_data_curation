import csv
import logging
from wikibaseintegrator import wbi_login, WikibaseIntegrator, wbi_enums
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.models import Qualifiers, References, Reference
from wikibaseintegrator.datatypes import (
    Item,
    ExternalID,
    Time,
    URL
)
from login import *
from helper import get_media_info_id
from tqdm import tqdm
from pathlib import Path
from wdcuration import query_wikidata, add_key_and_save_to_independent_dict
import json 
import random

HERE = Path(__file__).parent
DATA = HERE / "data"
DICTS = HERE / "dicts"

# Load configuration from config.json
def load_config():
    with open(HERE / "config.json", "r") as config_file:
        return json.load(config_file)

# Set configuration as global variables
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
CATEGORY_NAME = CATEGORY_RAW.replace("_", " ").replace("Category:", "").strip()

INSTITUTIONS_DICT = json.loads(DICTS.joinpath("institutions.json").read_text())

wbi_config['MEDIAWIKI_API_URL'] = 'https://commons.wikimedia.org/w/api.php'
wbi_config['SPARQL_ENDPOINT_URL'] = 'https://query.wikidata.org/sparql'
wbi_config['WIKIBASE_URL'] = 'https://commons.wikimedia.org'
wbi_config['USER_AGENT'] = 'TiagoLubiana (https://meta.wikimedia.org/wiki/User:TiagoLubiana)'


def generate_custom_edit_summary(test_edit=False):
    global SKIP_CREATOR
    # As per https://www.wikidata.org/wiki/Wikidata:Edit_groups/Adding_a_tool
    random_hex = f"{random.randrange(0, 2**48):x}"
    editgroup_snippet = f"([[:toolforge:editgroups-commons/b/CB/{random_hex}|details]])"
    skip_creator_snippet = ""
    if SKIP_CREATOR: 
        skip_creator_snippet = ", skipping creator statements"
        
    if test_edit:
         return f"SDC import (BHL Model v0.1.2, manual curation - tests{skip_creator_snippet})"
    else:
        return f"SDC import (BHL Model v0.1.2, manual curation{skip_creator_snippet}) {editgroup_snippet}"
    

def main(csv_path):

    logging.basicConfig(level=logging.INFO)

    login_instance = wbi_login.Login(
        user=USERNAME,
        password=PASSWORD,
        mediawiki_api_url=wbi_config['MEDIAWIKI_API_URL']
    )
    wbi = WikibaseIntegrator(login=login_instance)
    
    total_rows = sum(1 for _ in open(csv_path, encoding='utf-8-sig')) - 1
    edit_summary = generate_custom_edit_summary(test_edit=TEST)

    with open(csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter='\t')
        
        for row in tqdm(reader, desc="Processing rows", unit="rows", total=total_rows):

            file_name = row.get("File", "").strip()
            file_name_lower = file_name.lower()

            if file_name_lower.endswith(".pdf") or file_name_lower.endswith(".djvu"):
                logging.warning(f"Skipping row with PDF/DJVU file: {file_name}")
                continue

            if not file_name:
                logging.warning("Skipping row with empty 'File' column.")
                continue

            try:
                data = get_media_info_id(file_name)
                mediainfo_id = data
                media = wbi.mediainfo.get(entity_id=mediainfo_id)
            except Exception as e:
                if "The MW API returned that the entity was missing." in str(e):
                    media = wbi.mediainfo.new(id=mediainfo_id)
                else:
                    logging.error(f"Could not load MediaInfo for File:{file_name}: {e}")
                    continue

            new_statements = []

            add_instance_claim(row, new_statements, media)

            # Published in
            if not SKIP_PUBLISHED_IN:
                add_published_in_claim(row, new_statements)

            add_collection_claim(row, new_statements)
            if row["Sponsor"] =="":
                if ADD_EMPTY_IF_SPONSOR_MISSING:
                    add_blank_sponsor(row, new_statements)
                    
            add_digital_sponsor_claim(row, new_statements)
            
            add_bhl_id_claim(row, new_statements)
            add_flickr_id_claim(row, new_statements)
            if "P31" in media.claims.get_json():
                instance_of_value = media.claims.get_json()["P31"][0]["mainsnak"]["datavalue"]["value"]["id"]
                if instance_of_value in ["Q178659", "Q131597974"]:
                    # Either "Illustrated text" or "Illustration"
                    if not SKIP_CREATOR:
                        add_creator_statements(row, new_statements)
                    add_depicts_claim(row, new_statements)

                elif PHOTOGRAPHS_ONLY:
                    # e.g. for photos, skip or handle differently
                    pass

            else:
                if ALL_DRAWINGS:
                    if not SKIP_CREATOR:
                        add_creator_statements(row, new_statements)
                elif PHOTOGRAPHS_ONLY:
                    # e.g. for photos, skip or handle differently
                    pass
                elif row.get("Page Types", "") == "Illustration":
                        add_depicts_claim(row, new_statements)



            if not SKIP_DATES:
                add_inception_claim(row, new_statements)

            if new_statements:
                media.claims.add(new_statements, action_if_exists=wbi_enums.ActionIfExists.MERGE_REFS_OR_APPEND)
                try:
                    if TEST:
                        print(f"Check contributions on https://commons.wikimedia.org/wiki/Special:Contributions/{USERNAME}")
                        input("Press Enter to write SDC data...")
                    media.write(summary=edit_summary)
                    tqdm.write(f"No errors when trying to update {file_name} with SDC data.")
                except Exception as e:
                    logging.error(f"Failed to write SDC for {file_name}: {e}")
            else:
                logging.info(f"No SDC data to add for {file_name}, skipping...")

def add_creator_statements(row, new_statements):
    add_illustrator_claim(row, new_statements)
    add_engraver_claim(row, new_statements)
    add_lithographer_claim(row, new_statements)
    add_painter_claim(row, new_statements)

def get_qid_from_flickr_binomial_tags(flickr_tags):
    qids = []
    for tag in flickr_tags:
        # Example tag + " 'taxonomy:binomial=Psittacus cyanogaster'"
        if "taxonomy:binomial=" in tag:
            # remove all non-alphanumeric characters
            taxon_name = tag.split("taxonomy:binomial=")[1].strip().replace("'", "")
            taxon_name = ''.join(e for e in taxon_name if e.isalnum() or e == " ")
            qid = get_qid_from_taxon_name(taxon_name)
            if qid:
                qids.append(qid)
    return qids

def get_qid_from_taxon_name(taxon_name):
    query = f"""
    SELECT ?item WHERE {{
        ?item wdt:P225 "{taxon_name}".
    }}
    """
    result = query_wikidata(query)
    if len(result) == 1:
        return result[0]["item"].replace("http://www.wikidata.org/entity/", "")
    return ""

def add_depicts_claim(row, new_statements, set_prominent=SET_PROMINENT):
    names = row.get("Names", "").strip().split("; ")
    if set_prominent:
        rank = "preferred"
    else:
        rank = "normal"
    if names:
        bhl_page_id = row.get("BHL Page ID", "").strip()
        if bhl_page_id:
           for name in names:
            if len(name.split(" ")) == 1:
                # If only one word, it's probably a genus, skip
                continue
            qid = get_qid_from_taxon_name(name)
            if qid:

                claim_depicts = Item(prop_nr="P180", value=qid, rank=rank)
                references = References()
                ref_obj = Reference()
                ref_obj.add(Item(prop_nr="P887", value="Q132359710")) # Inferred from the BHL OCR
                ref_obj.add(URL(prop_nr="P854", value=f"https://biodiversitylibrary.org/page/{bhl_page_id}"))
                references.add(ref_obj)
                claim_depicts.references = references
                new_statements.append(claim_depicts)
    flickr_tags = row.get("Flickr Tags", "").strip().split(",")
    flickr_id = row.get("Flickr ID", "").strip()
    if flickr_tags:
        qids = get_qid_from_flickr_binomial_tags(flickr_tags)
        for qid in qids:
            if len(qids) > 1:
                rank = "normal"
            claim_depicts = Item(prop_nr="P180", value=qid, rank=rank)
            references = References()
            ref_obj = Reference()
            ref_obj.add(Item(prop_nr="P887", value="Q131782980")) # Inferred from Flickr tag
            ref_obj.add(URL(prop_nr="P854", value=f"https://www.flickr.com/photo.gne?id={flickr_id}"))
            references.add(ref_obj)
            claim_depicts.references = references
            new_statements.append(claim_depicts)

def add_inception_claim(row, new_statements):
    inception_str = row.get("Item Publication Date", "").strip()
    if inception_str:
        if len(inception_str) != 4 or not inception_str.isdigit():
            logging.warning(f"Invalid year format for inception date: {inception_str}")
            return
        
        formatted_string = f"+{inception_str}-01-01T00:00:00Z"
        claim_inception = Time(
            prop_nr="P571",
            time=formatted_string,
            precision=wbi_enums.WikibaseTimePrecision.YEAR
        )
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P1480", value="Q110290992"))  # no later than
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))   # analog work
        claim_inception.qualifiers = qualifiers

        # reference: P887 = Q110393725 (inferred from publication date)
        references = References()
        ref_obj = Reference()
        ref_obj.add(Item(prop_nr="P887", value="Q110393725"))
        item_id = row.get("Item ID", "").strip()
        if item_id:
            ref_obj.add(URL(prop_nr="P854", value=f"https://www.biodiversitylibrary.org/item/{item_id}"))
        references.add(ref_obj)
        claim_inception.references = references
        new_statements.append(claim_inception)


def add_painter_claim(row, new_statements):
    painter = row.get("Painter", "").strip()
    if painter:
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        qualifiers.add(Item(prop_nr="P3831", value="Q1028181"))    # painter

        references = References()
        ref_url = row.get("Ref URL for Authors", "").strip()
        if ref_url:
            ref_obj = Reference()
            ref_obj.add(URL(prop_nr="P854", value=ref_url))
            references.add(ref_obj)

        claim_painter = Item(
            prop_nr="P170",
            value=painter,
            qualifiers=qualifiers,
            references=references
        )
        new_statements.append(claim_painter)

def add_illustrator_claim(row, new_statements):
    illustrator = row.get("Illustrator", "").strip()
    if illustrator:
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        qualifiers.add(Item(prop_nr="P3831", value="Q644687"))    # illustrator

        references = References()
        ref_url = row.get("Ref URL for Authors", "").strip()
        if ref_url:
            ref_obj = Reference()
            ref_obj.add(URL(prop_nr="P854", value=ref_url))
            references.add(ref_obj)

        claim_creator = Item(
            prop_nr="P170",
            value=illustrator,
            qualifiers=qualifiers,
            references=references
        )
        new_statements.append(claim_creator)

def add_lithographer_claim(row, new_statements):
    lithographer = row.get("Lithographer", "").strip()
    if lithographer:
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        qualifiers.add(Item(prop_nr="P3831", value="Q16947657"))    # lithographer

        references = References()
        ref_url = row.get("Ref URL for Authors", "").strip()
        if ref_url:
            ref_obj = Reference()
            ref_obj.add(URL(prop_nr="P854", value=ref_url))
            references.add(ref_obj)

        claim_lithographer = Item(
            prop_nr="P170",
            value=lithographer,
            qualifiers=qualifiers,
            references=references
        )
        new_statements.append(claim_lithographer)

def add_engraver_claim(row, new_statements):
    engraver = row.get("Engraver", "").strip()
    if engraver:
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        qualifiers.add(Item(prop_nr="P3831", value="Q329439"))    # engraver

        references = References()
        ref_url = row.get("Ref URL for Authors", "").strip()
        if ref_url:
            ref_obj = Reference()
            ref_obj.add(URL(prop_nr="P854", value=ref_url))
            references.add(ref_obj)

        claim_engraver = Item(
            prop_nr="P170",
            value=engraver,
            qualifiers=qualifiers,
            references=references
        )
        new_statements.append(claim_engraver)

def add_flickr_id_claim(row, new_statements):
    flickr_id = row.get("Flickr ID", "").strip()
    if flickr_id:
        claim_flickr = ExternalID(prop_nr="P12120", value=flickr_id)
        new_statements.append(claim_flickr)
def add_bhl_id_claim(row, new_statements):
    bhl_page_id = row.get("BHL Page ID", "").strip()
    if bhl_page_id:
        claim_bhl = ExternalID(prop_nr="P687", value=bhl_page_id)
        new_statements.append(claim_bhl)

def add_blank_sponsor(row, new_statements):
    qualifiers = Qualifiers()
    qualifiers.add(Item(prop_nr="P3831", value="Q131344184"))  # digitization sponsor

    references = References()
    bib_id = row.get("Bibliography ID", "").strip()
    if bib_id:
        ref_obj = Reference()
        ref_obj.add(URL(prop_nr="P854", value=f"https://www.biodiversitylibrary.org/bibliography/{bib_id}"))
        references.add(ref_obj)

    claim_sponsor = Item(
        prop_nr="P859",
        snaktype="somevalue",
        qualifiers=qualifiers,
        references=references
    )
    new_statements.append(claim_sponsor)

def add_digital_sponsor_claim(row, new_statements):
    sponsor = row.get("Sponsor", "").strip()
    if sponsor:
        sponsor = get_institution_as_a_qid(sponsor)

        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P3831", value="Q131344184"))  # digitization sponsor

        references = References()
        bib_id = row.get("Bibliography ID", "").strip()
        if bib_id:
            ref_obj = Reference()
            ref_obj.add(URL(prop_nr="P854", value=f"https://www.biodiversitylibrary.org/bibliography/{bib_id}"))
            references.add(ref_obj)

        claim_sponsor = Item(
            prop_nr="P859",
            value=sponsor,
            qualifiers=qualifiers,
            references=references
        )
        new_statements.append(claim_sponsor)

def add_collection_claim(row, new_statements):
    collection = row.get("Collection", "").strip()
    if collection:
        collection = get_institution_as_a_qid(collection)

        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P3831", value="Q131597993"))  # holding institution

        references = References()
        bib_id = row.get("Bibliography ID", "").strip()
        if bib_id:
            ref_obj = Reference()
            ref_obj.add(URL(prop_nr="P854", value=f"https://www.biodiversitylibrary.org/bibliography/{bib_id}"))
            references.add(ref_obj)

        claim_collection = Item(
            prop_nr="P195",
            value=collection,
            qualifiers=qualifiers,
            references=references
        )
        new_statements.append(claim_collection)

def get_institution_as_a_qid(collection):
    global INSTITUTIONS_DICT
    if collection in INSTITUTIONS_DICT:
        collection = INSTITUTIONS_DICT[collection]
        
        # test if collection is a QID
    if not collection.startswith("Q"):
        INSTITUTIONS_DICT=  add_key_and_save_to_independent_dict(
                dictionary=INSTITUTIONS_DICT, 
                dictionary_path=DICTS.joinpath("institutions.json"),
                string=collection)
        collection = INSTITUTIONS_DICT[collection]
    return collection

def add_instance_claim(row, new_statements, media):
    global ALL_DRAWINGS
    global SKIP_EXISTING_INSTANCE_OF
    if SKIP_EXISTING_INSTANCE_OF:
        if "P31" in media.claims.get_json():
                return 1
    if ALL_DRAWINGS == True:
        claim_instance_of = Item(prop_nr="P31", value="Q178659")
        new_statements.append(claim_instance_of)
        return 1
    if row.get("Page Types") == "Illustration":
        claim_instance_of = Item(prop_nr="P31", value="Q178659")
        new_statements.append(claim_instance_of)
        return 1
    if row.get("Page Types") == "Table of Contents":
        claim_instance_of = Item(prop_nr="P31", value="Q1456936")
        new_statements.append(claim_instance_of)
        return 1

def add_published_in_claim(row, new_statements):
    published_in = row.get("Published In QID", "").strip()
    if published_in:
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        references = References()
        bib_id = row.get("Bibliography ID", "").strip()
        if bib_id:
            ref_obj = Reference()
            ref_obj.add(URL(prop_nr="P854", value=f"https://www.biodiversitylibrary.org/bibliography/{bib_id}"))
            references.add(ref_obj)
        claim_published_in = Item(
            prop_nr="P1433",
            value=published_in,
            qualifiers=qualifiers,
            references=references
        )
        new_statements.append(claim_published_in)

        

if __name__ == "__main__":
    main(DATA / f"{CATEGORY_NAME.replace(' ', '_')}.tsv")
