import csv
import logging
import json
import argparse

from tqdm import tqdm
from pathlib import Path

import pandas as pd

from wikibaseintegrator import wbi_login, WikibaseIntegrator, wbi_enums
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.models import Qualifiers, References, Reference
from wikibaseintegrator.datatypes import Item, ExternalID, Time, URL, String
from wdcuration import add_key_and_save_to_independent_dict, lookup_id

from login import *
from helper import (
    get_media_info_id,
    get_wikidata_qid_from_gbif,
    generate_custom_edit_summary,
)

NO_PHOTOGRAPHS = False

HERE = Path(__file__).parent
DATA = HERE / "data"
DICTS = HERE / "dicts"
LIST_OF_PLATE_PREFIXES = ["Pl.", "Tab.", "Taf."]
INSTITUTIONS_DICT = json.loads(DICTS.joinpath("institutions.json").read_text())

wbi_config["MEDIAWIKI_API_URL"] = "https://commons.wikimedia.org/w/api.php"
wbi_config["SPARQL_ENDPOINT_URL"] = "https://query.wikidata.org/sparql"
wbi_config["WIKIBASE_URL"] = "https://commons.wikimedia.org"
wbi_config["USER_AGENT"] = (
    "TiagoLubiana (https://meta.wikimedia.org/wiki/User:TiagoLubiana)"
)


def load_config(config_file_name):
    with open(HERE / config_file_name, "r") as config_file:
        return json.load(config_file)


def upload_metadata_to_commons(csv_path):

    logging.basicConfig(level=logging.INFO)
    login_instance = wbi_login.Login(
        user=USERNAME,
        password=PASSWORD,
        mediawiki_api_url=wbi_config["MEDIAWIKI_API_URL"],
    )
    wbi = WikibaseIntegrator(login=login_instance)

    wiki_edit_summary = generate_custom_edit_summary()

    metadata_df = pd.read_csv(csv_path, sep="\t", dtype=str)
    metadata_df.fillna("", inplace=True)

    for i, row in tqdm(metadata_df.iterrows()):
        file_name = row["File"].strip()
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
        claims = media.claims.get_json()

        # skipping most info if mimimum statements are in (instance of, published in, bhl page id, collection, sponsor)
        minimal_statements = ["P31", "P1433", "P687", "P195", "P859"]
        if all(claim in claims for claim in minimal_statements):
            logging.info(f"Skipping {file_name} because it already has minimum data.")

            # Always adding depicts information
            add_depicts_claim(row, new_statements, media)
            if new_statements:
                media.claims.add(
                    new_statements,
                    action_if_exists=wbi_enums.ActionIfExists.MERGE_REFS_OR_APPEND,
                )
                media.write(summary=wiki_edit_summary)
                logging.info(
                    f"Added depicts statement to {file_name} because it already has minimum data."
                )

            # Always adding public domain statement, replacing all other information
            add_public_domain_statement(row, media, new_statements)
            if new_statements:
                media.claims.add(
                    new_statements,
                    action_if_exists=wbi_enums.ActionIfExists.REPLACE_ALL,
                )
                media.write(summary=wiki_edit_summary)
                logging.info(
                    f"Added public domain statement to {file_name} because it already has minimum data."
                )
            continue

        add_instance_claim(row, new_statements, media)
        add_public_domain_statement(row, media, new_statements)
        add_published_in_claim(row, new_statements, media)
        add_collection_claim(row, new_statements)
        if row["Sponsor"] == "":
            add_blank_sponsor(row, new_statements)
        add_digital_sponsor_claim(row, new_statements)
        add_bhl_id_claim(row, new_statements)
        add_flickr_id_claim(row, new_statements)
        if "P31" in claims:
            instance_of_value = claims["P31"][0]["mainsnak"]["datavalue"]["value"]["id"]
            if instance_of_value in ["Q178659", "Q131597974"]:
                # Either "Illustrated text" or "Illustration"
                if not SKIP_CREATOR:
                    add_creator_statements(row, new_statements)
                add_depicts_claim(row, new_statements, media)

        else:
            if row.get("Page Types", "") == "Illustration":
                add_creator_statements(row, new_statements)
                add_depicts_claim(row, new_statements, media)

        if not SKIP_DATES:
            add_inception_claim(row, media, new_statements)

        if new_statements:
            media.claims.add(
                new_statements,
                action_if_exists=wbi_enums.ActionIfExists.MERGE_REFS_OR_APPEND,
            )
            try:
                if TEST:
                    print(
                        f"Check contributions on https://commons.wikimedia.org/wiki/Special:Contributions/{USERNAME}"
                    )
                    input("Press Enter to write SDC data...")
                media.write(summary=wiki_edit_summary)
                tqdm.write(
                    f"No errors when trying to update {file_name} with SDC data."
                )
            except Exception as e:
                logging.error(f"Failed to write SDC for {file_name}: {e}")
        else:
            logging.info(f"No SDC data to add for {file_name}, skipping...")


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


def add_creator_statements(row, new_statements):
    # Avoid adding creator statements for extracted images; some are e.g monograms
    is_extracted = row.get("Is Extracted", "").strip()
    if is_extracted == "True":
        return
    add_illustrator_claim(row, new_statements)
    add_engraver_claim(row, new_statements)
    add_lithographer_claim(row, new_statements)
    add_painter_claim(row, new_statements)
    flickr_tags = row.get("Flickr Tags", "").strip().split(",")
    flickr_id = row.get("Flickr ID", "").strip()
    illustrator_qids = get_illustrator_qid_from_flickr_illustrator_tags(flickr_tags)
    for qid in illustrator_qids:
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        qualifiers.add(Item(prop_nr="P3831", value="Q644687"))  # illustrator

        references = References()
        ref_obj = Reference()
        ref_obj.add(
            Item(prop_nr="P887", value="Q131782980")
        )  # Inferred from Flickr tag
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
        ref_obj.add(
            Item(prop_nr="P887", value="Q131782980")
        )  # Inferred from Flickr tag
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


def add_painter_claim(row, new_statements):
    painter = row.get("Painter", "").strip()
    if painter:
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        qualifiers.add(Item(prop_nr="P3831", value="Q1028181"))  # painter

        references = References()
        ref_url = row.get("Ref URL for Authors", "").strip()
        if ref_url:
            ref_obj = Reference()
            ref_obj.add(URL(prop_nr="P854", value=ref_url))
            references.add(ref_obj)

        claim_painter = Item(
            prop_nr="P170", value=painter, qualifiers=qualifiers, references=references
        )
        new_statements.append(claim_painter)


def add_illustrator_claim(row, new_statements):
    illustrator = row.get("Illustrator", "").strip()
    if illustrator:
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        qualifiers.add(Item(prop_nr="P3831", value="Q644687"))  # illustrator

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
            references=references,
        )
        new_statements.append(claim_creator)


def add_lithographer_claim(row, new_statements):
    lithographer = row.get("Lithographer", "").strip()
    if lithographer:
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        qualifiers.add(Item(prop_nr="P3831", value="Q16947657"))  # lithographer

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
            references=references,
        )
        new_statements.append(claim_lithographer)


def add_engraver_claim(row, new_statements):
    engraver = row.get("Engraver", "").strip()
    if engraver:
        qualifiers = Qualifiers()
        qualifiers.add(Item(prop_nr="P518", value="Q112134971"))  # analog work
        qualifiers.add(Item(prop_nr="P3831", value="Q329439"))  # engraver

        references = References()
        ref_url = row.get("Ref URL for Authors", "").strip()
        if ref_url:
            ref_obj = Reference()
            ref_obj.add(URL(prop_nr="P854", value=ref_url))
            references.add(ref_obj)

        claim_engraver = Item(
            prop_nr="P170", value=engraver, qualifiers=qualifiers, references=references
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
    page_type = row.get("Page Types")

    if page_type == "Text Illustration":
        return 1  # I've noticed that the presence of both may related to many different kinds of images, so I'm skipping this for now

    if page_type in page_type_to_qid:
        if page_type == "Illustration":
            try:
                if (
                    int(row.get("Item Publication Date", "").strip()) < 1843
                    or NO_PHOTOGRAPHS
                ):
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


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Generate metadata for BHL images.")
    parser.add_argument(
        "--auto_mode", action="store_true", help="Use auto mode configuration."
    )
    parser.add_argument(
        "--category_raw", type=str, help="Specify the raw category name."
    )
    args = parser.parse_args()

    if args.auto_mode:
        config_file = "config_auto.json"
        test = input(
            "Proceed with upload? Press anything to continue, or Ctrl+C to cancel."
        )
        print(
            "Remember: on Linux, you may use Ctrl+S to pause the processing and Ctrl+Q to resume."
        )
    else:
        config_file = "config.json"

    config = load_config(config_file)

    TEST = config["TEST"]
    SKIP_CREATOR = config["SKIP_CREATOR"]
    INFER_BHL_PAGE_FROM_FLICKR_ID = config["INFER_BHL_PAGE_FROM_FLICKR_ID"]
    INFER_FROM_INTERNET_ARCHIVE = config["INFER_FROM_INTERNET_ARCHIVE"]
    INTERNET_ARCHIVE_OFFSET = config["INTERNET_ARCHIVE_OFFSET"]
    ILLUSTRATOR = config["ILLUSTRATOR"]
    PAINTER = config["PAINTER"]
    ENGRAVER = config["ENGRAVER"]
    LITHOGRAPHER = config["LITHOGRAPHER"]
    REF_URL_FOR_AUTHORS = config["REF_URL_FOR_AUTHORS"]
    COMMONS_API_ENDPOINT = config["COMMONS_API_ENDPOINT"]
    WIKIDATA_SPARQL_ENDPOINT = config["WIKIDATA_SPARQL_ENDPOINT"]
    BHL_BASE_URL = config["BHL_BASE_URL"]
    SKIP_DATES = config["SKIP_DATES"]

    if args.category_raw:
        CATEGORY_RAW = args.category_raw
        config["CATEGORY_RAW"] = CATEGORY_RAW
    else:
        CATEGORY_RAW = config["CATEGORY_RAW"]

    CATEGORY_NAME = CATEGORY_RAW.replace("_", " ").replace("Category:", "").strip()

    output_file = DATA / f"{CATEGORY_NAME.replace(' ', '_')}.tsv"

    upload_metadata_to_commons(output_file)
