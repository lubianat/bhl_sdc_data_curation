import requests
import json
import logging

from wikibaseintegrator.datatypes import Item, ExternalID, Time, URL, String
from wikibaseintegrator.models import Qualifiers, References, Reference
from wikibaseintegrator.models import Qualifiers, References, Reference
from wikibaseintegrator.datatypes import Item, ExternalID, Time, URL, String
from wdcuration import add_key_and_save_to_independent_dict, lookup_id
from wikibaseintegrator import wbi_enums

import random
from pathlib import Path


HERE = Path(__file__).parent
DATA = HERE / "data"
DICTS = HERE / "dicts"
LIST_OF_PLATE_PREFIXES = ["Pl.", "Tab.", "Taf."]
INSTITUTIONS_DICT = json.loads(DICTS.joinpath("institutions.json").read_text())

COMMONS_API_ENDPOINT = "https://commons.wikimedia.org/w/api.php"

logging.basicConfig(level=logging.INFO)


def set_up_wbi_config(wbi_config):
    wbi_config["MEDIAWIKI_API_URL"] = "https://commons.wikimedia.org/w/api.php"
    wbi_config["SPARQL_ENDPOINT_URL"] = "https://query.wikidata.org/sparql"
    wbi_config["WIKIBASE_URL"] = "https://commons.wikimedia.org"
    wbi_config["USER_AGENT"] = (
        "TiagoLubiana (https://meta.wikimedia.org/wiki/User:TiagoLubiana)"
    )

def load_config(config_file_name):
    with open(HERE / config_file_name, "r") as config_file:
        return json.load(config_file)


# Wikibase editing functions


def get_artist_qids_from_flickr_tags(flickr_tags):
    qids = []
    for tag in flickr_tags:
        # Example tag + " 'taxonomy:binomial=Psittacus cyanogaster'"
        if "artist:wikidata=" in tag:
            # remove all non-alphanumeric characters
            qid = tag.split("artist:wikidata=")[1].strip().replace("'", "")
            if qid:
                qids.append(qid)
        elif "artist:viaf" in tag:
            # remove all non-alphanumeric characters
            viaf = tag.split("artist:viaf=")[1].strip().replace("'", "")
            qid = lookup_id(viaf, "P214")
            if qid:
                qids.append(qid)
    return qids


def get_illustrator_qid_from_flickr_illustrator_tags(flickr_tags):
    qids = []
    for tag in flickr_tags:
        # Example tag + " 'taxonomy:binomial=Psittacus cyanogaster'"
        if "illustrator:wikidata=" in tag:
            # remove all non-alphanumeric characters
            qid = tag.split("illustrator:wikidata=")[1].strip().replace("'", "")
            if qid:
                qids.append(qid)
    return qids


def get_species_names_from_flickr_binomial_tags(flickr_tags):
    names = []
    for tag in flickr_tags:
        # Example tag + " 'taxonomy:binomial=Psittacus cyanogaster'"
        tag = tag.replace("Taxonomy:binomial=", "taxonomy:binomial=")
        if "taxonomy:binomial=" in tag:
            # remove all non-alphanumeric characters
            taxon_name = tag.split("taxonomy:binomial=")[1].strip().replace("'", "")
            taxon_name = "".join(e for e in taxon_name if e.isalnum() or e == " ")
            # Skip if it is only a genus
            if len(taxon_name.split(" ")) == 1:
                continue
            if taxon_name:
                names.append(taxon_name)
    return names


def add_depicts_claim(row, new_statements, media):

    rank = "preferred"
    bhl_names = row.get("Names", "").strip().split("; ")

    is_extracted = row.get("Is Extracted", "").strip()
    if (
        is_extracted == "True"
    ):  # Avoid adding depicts statements for extracted images; some are e.g monograms
        return

    current_p180_qids = []
    claims_in_media = media.claims.get_json()
    if "P180" in claims_in_media:
        p180_values = claims_in_media["P180"]
        current_p180_qids = [
            value["mainsnak"]["datavalue"]["value"]["id"] for value in p180_values
        ]

    if bhl_names:
        bhl_page_id = row.get("BHL Page ID", "").strip()
        if bhl_page_id:
            if len(bhl_names) > 1:
                rank = "normal"
            for name in bhl_names:
                if name == "":
                    continue

                references = References()
                ref_obj = Reference()
                ref_obj.add(
                    Item(prop_nr="P887", value="Q132907038")
                )  # INFERRED FROM GBIF SCIENTIFIC NAME MATCHING SERVICES
                ref_obj.add(
                    String(prop_nr="P5997", value=name)
                )  # Object stated in reference as
                if len(name.split(" ")) == 1:
                    # If only one word, it's probably a genus, skip
                    continue
                qid = get_wikidata_qid_from_gbif(name)
                if qid and qid not in current_p180_qids:
                    claim_depicts = Item(prop_nr="P180", value=qid, rank=rank)
                    ref_obj.add(
                        Item(prop_nr="P887", value="Q132359710")
                    )  # Inferred from the BHL OCR
                    ref_obj.add(
                        URL(
                            prop_nr="P854",
                            value=f"https://biodiversitylibrary.org/page/{bhl_page_id}",
                        )
                    )
                    references.add(ref_obj)
                    claim_depicts.references = references
                    new_statements.append(claim_depicts)
    flickr_tags = row.get("Flickr Tags", "").strip().split(",")
    flickr_id = row.get("Flickr ID", "").strip()
    if flickr_tags:
        flickr_species_names = get_species_names_from_flickr_binomial_tags(flickr_tags)
        if len(flickr_species_names) > 1:
            rank = "normal"
        for name in flickr_species_names:
            qid = get_wikidata_qid_from_gbif(name)
            if qid and qid not in current_p180_qids:
                references = References()
                ref_obj = Reference()
                ref_obj.add(
                    Item(prop_nr="P887", value="Q132907038")
                )  # INFERRED FROM GBIF SCIENTIFIC NAME MATCHING SERVICES
                ref_obj.add(String(prop_nr="P5997", value=name))
                claim_depicts = Item(prop_nr="P180", value=qid, rank=rank)
                ref_obj.add(
                    Item(prop_nr="P887", value="Q131782980")
                )  # Inferred from Flickr tag
                ref_obj.add(
                    URL(
                        prop_nr="P854",
                        value=f"https://www.flickr.com/photo.gne?id={flickr_id}",
                    )
                )
                references.add(ref_obj)
                claim_depicts.references = references
                new_statements.append(claim_depicts)


def add_creator_statements(row, new_statements):
    # Avoid adding creator statements for extracted images; some are e.g monograms
    is_extracted = row.get("Is Extracted", "").strip()
    if is_extracted == "True":
        return
    flickr_tags = row.get("Flickr Tags", "").strip().split(",")
    flickr_id = row.get("Flickr ID", "").strip()
    illustrator_qids = get_illustrator_qid_from_flickr_illustrator_tags(flickr_tags)
    for qid in illustrator_qids:
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        qualifiers.add(Item(prop_nr="P3831", value="Q644687"))  # illustrator

        references = References()
        ref_obj = Reference()
        # Inferred from Flickr tag
        ref_obj.add(Item(prop_nr="P887", value="Q131782980"))
        ref_obj.add(
            URL(
                prop_nr="P854", value=f"https://www.flickr.com/photo.gne?id={flickr_id}"
            )
        )
        references.add(ref_obj)

        claim_creator = Item(
            prop_nr="P170", value=qid, qualifiers=qualifiers, references=references
        )
        new_statements.append(claim_creator)
    artist_qids = get_artist_qids_from_flickr_tags(flickr_tags)
    for qid in artist_qids:
        if qid in illustrator_qids:
            continue
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        qualifiers.add(Item(prop_nr="P3831", value="Q483501"))  # artist

        references = References()
        ref_obj = Reference()
        # Inferred from Flickr tag
        ref_obj.add(Item(prop_nr="P887", value="Q131782980"))
        ref_obj.add(
            URL(
                prop_nr="P854", value=f"https://www.flickr.com/photo.gne?id={flickr_id}"
            )
        )
        references.add(ref_obj)

        claim_creator_artist = Item(
            prop_nr="P170", value=qid, qualifiers=qualifiers, references=references
        )
        new_statements.append(claim_creator_artist)


def add_public_domain_statement(row, media, new_statements):
    copyright_status = row.get("Copyright Status", "")
    if (
        copyright_status == "NOT_IN_COPYRIGHT"
        or "Public domain. The BHL considers that this work is no longer under copyright protection."
    ):
        references = References()
        ref_obj = Reference()
        ref_obj.add(
            URL(
                prop_nr="P854",
                value=f"https://www.biodiversitylibrary.org/bibliography/{row.get('Bibliography ID', '')}",
            )
        )
        references.add(ref_obj)

        copyright_status_qid = "Q19652"  # Setting the value to "public domain"
        # This was decided on the 2025-03-17 BHL-Wiki meeting

        copyright_status_claim = Item(
            prop_nr="P6216", value=copyright_status_qid, references=references
        )
        # Remove lingering "copyrighted" or "cc-by" statements:
        claims_p6216 = media.claims.get("P6216")
        for claim in claims_p6216:
            claim_p6216_id = claim.mainsnak.datavalue.get("value").get("id")
            if claim_p6216_id and claim_p6216_id != "Q19652":
                claim.remove()

        claims_p275 = media.claims.get("P275")
        for claim in claims_p275:
            claim.remove()
        new_statements.append(copyright_status_claim)


def add_inception_claim(row, media, new_statements):
    inception_str = row.get("Item Publication Date", "").strip()
    claims_in_media = media.claims.get_json()
    current_p571_dates = []
    if "P571" in claims_in_media:
        p571_values = claims_in_media["P571"]
        current_p571_dates = [
            value["mainsnak"]["datavalue"]["value"]["time"][1:5]
            for value in p571_values
        ]

    if inception_str and inception_str not in current_p571_dates:
        if len(inception_str) != 4 or not inception_str.isdigit():
            logging.warning(f"Invalid year format for inception date: {inception_str}")
            return

        formatted_string = f"+{inception_str}-01-01T00:00:00Z"
        claim_inception = Time(
            prop_nr="P571",
            time=formatted_string,
            precision=wbi_enums.WikibaseTimePrecision.YEAR,
        )
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P1480", value="Q110290992"))  # no later than
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        claim_inception.qualifiers = qualifiers

        # reference: P887 = Q110393725 (inferred from publication date)
        references = References()
        ref_obj = Reference()
        ref_obj.add(Item(prop_nr="P887", value="Q110393725"))
        item_id = row.get("Item ID", "").strip()
        if item_id:
            ref_obj.add(
                URL(
                    prop_nr="P854",
                    value=f"https://www.biodiversitylibrary.org/item/{item_id}",
                )
            )
        references.add(ref_obj)
        claim_inception.references = references
        new_statements.append(claim_inception)


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
        ref_obj.add(
            URL(
                prop_nr="P854",
                value=f"https://www.biodiversitylibrary.org/bibliography/{bib_id}",
            )
        )
        references.add(ref_obj)

    claim_sponsor = Item(
        prop_nr="P859",
        snaktype="somevalue",
        qualifiers=qualifiers,
        references=references,
    )
    new_statements.append(claim_sponsor)


def add_digital_sponsor_claim(row, new_statements):
    sponsor = row.get("Sponsor", "").strip()
    if sponsor:
        sponsor = get_institution_as_a_qid(sponsor)

        qualifiers = Qualifiers()
        qualifiers.add(
            Item(prop_nr="P3831", value="Q131344184")
        )  # digitization sponsor

        references = References()
        bib_id = row.get("Bibliography ID", "").strip()
        if bib_id:
            ref_obj = Reference()
            ref_obj.add(
                URL(
                    prop_nr="P854",
                    value=f"https://www.biodiversitylibrary.org/bibliography/{bib_id}",
                )
            )
            references.add(ref_obj)

        claim_sponsor = Item(
            prop_nr="P859", value=sponsor, qualifiers=qualifiers, references=references
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
            ref_obj.add(
                URL(
                    prop_nr="P854",
                    value=f"https://www.biodiversitylibrary.org/bibliography/{bib_id}",
                )
            )
            references.add(ref_obj)

        claim_collection = Item(
            prop_nr="P195",
            value=collection,
            qualifiers=qualifiers,
            references=references,
        )
        new_statements.append(claim_collection)


def get_institution_as_a_qid(collection):
    global INSTITUTIONS_DICT
    if collection in INSTITUTIONS_DICT:
        collection = INSTITUTIONS_DICT[collection]

        # test if collection is a QID
    if not collection.startswith("Q"):
        INSTITUTIONS_DICT = add_key_and_save_to_independent_dict(
            dictionary=INSTITUTIONS_DICT,
            dictionary_path=DICTS.joinpath("institutions.json"),
            string=collection,
        )
        collection = INSTITUTIONS_DICT[collection]
    return collection


def add_instance_claim(row, new_statements, media):

    # By default, skip adding instances if some instance is present
    if "P31" in media.claims.get_json():
        return 1

    page_type_to_qid = {
        "Illustration": "Q178659",  # "ilustration", used in this context only for drawings
        "Table of Contents": "Q1456936",
        "Foldout": "Q2649400",
        "Map": "Q4006",
        "Title Page": "Q1339862",
    }

    # Only add Illustration if work is older than 1843 (as after that, it may be a photograph!)
    page_type = row["Page Types"]

    if page_type == "Text Illustration":
        return 1  # I've noticed that the presence of both may related to many different kinds of images, so I'm skipping this for now

    if page_type in page_type_to_qid:
        if page_type == "Illustration":
            try:
                if int(row["Item Publication Date"].strip()) < 1843:
                    claim_instance_of = Item(
                        prop_nr="P31", value=page_type_to_qid[page_type]
                    )
                    new_statements.append(claim_instance_of)
                    return 1
            except:
                pass
        else:
            claim_instance_of = Item(prop_nr="P31", value=page_type_to_qid[page_type])
            new_statements.append(claim_instance_of)
            return 1


def add_published_in_claim(row, new_statements, media):
    # Test
    published_in = row.get("Published In QID", "").strip()
    claims = media.claims.get_json()
    if "P1433" in claims:
        for publication_entry in claims["P1433"]:
            try:

                if (
                    publication_entry["mainsnak"]["datavalue"]["value"]["id"]
                    == published_in
                ):
                    return 1
            except:
                continue
    if published_in:
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        volume = row["Volume"]
        if volume:
            volume = volume.strip()
            qualifiers.add(String(prop_nr="P478", value=volume))

        page_number_prefix = row.get("Page Number Prefix", "").strip()
        page_number_number = row.get("Page Number Number", "").strip()
        if page_number_prefix and page_number_number:
            if page_number_prefix in LIST_OF_PLATE_PREFIXES:
                qualifiers.add(String(prop_nr="P12275", value=page_number_number))

        references = References()
        bhl_page_id = row.get("BHL Page ID", "").strip()
        if bhl_page_id:
            ref_obj = Reference()
            ref_obj.add(
                URL(
                    prop_nr="P854",
                    value=f"https://www.biodiversitylibrary.org/page/{bhl_page_id}",
                )
            )
            references.add(ref_obj)
        claim_published_in = Item(
            prop_nr="P1433",
            value=published_in,
            qualifiers=qualifiers,
            references=references,
        )
        new_statements.append(claim_published_in)


# General helper functions


def generate_custom_edit_summary():
    # As per https://www.wikidata.org/wiki/Wikidata:Edit_groups/Adding_a_tool
    random_hex = f"{random.randrange(0, 2**48):x}"
    editgroup_snippet = f"([[:toolforge:editgroups-commons/b/CB/{random_hex}|details]])"
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
