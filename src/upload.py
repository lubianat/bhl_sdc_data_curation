import csv
import logging
import json
import argparse

from tqdm import tqdm
from pathlib import Path

import pandas as pd

from wikibaseintegrator import wbi_login, WikibaseIntegrator, wbi_enums
from wikibaseintegrator.wbi_config import config as wbi_config

from login import *
from helper import (
    load_config,
    get_media_info_id,
    generate_custom_edit_summary,
    add_public_domain_statement,
    add_creator_statements,
    add_depicts_claim,
    add_bhl_id_claim,
    add_blank_sponsor,
    add_collection_claim,
    add_digital_sponsor_claim,
    add_flickr_id_claim,
    add_inception_claim,
    add_instance_claim,
    add_published_in_claim,
    set_up_wbi_config,
)

HERE = Path(__file__).parent
DATA = HERE / "data"
DICTS = HERE / "dicts"

set_up_wbi_config(wbi_config)


def upload_metadata_to_commons(csv_path):

    logging.basicConfig(level=logging.INFO)
    login_instance = wbi_login.Login(
        user=USERNAME,
        password=PASSWORD,
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

        bhl_page_id = row["BHL Page ID"].strip()
        try:
            flickr_id = row["Flickr ID"].strip()
        except:
            flickr_id = ""

        file_is_likely_a_crop = True  # Assume it is a crop for safety

        if bhl_page_id in file_name:
            file_is_likely_a_crop = False
        if flickr_id != "" and flickr_id not in file_name:
            file_is_likely_a_crop = False
        if "(cropped)" in file_name:
            file_is_likely_a_crop = True

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

            # Always adding depicts information (unless file is a crop)
            if not file_is_likely_a_crop:
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

        if not file_is_likely_a_crop:
            if row.get("Page Types", "") == "Illustration":
                add_creator_statements(row, new_statements)
                add_depicts_claim(row, new_statements, media)

        add_inception_claim(row, media, new_statements)

        if new_statements:
            media.claims.add(
                new_statements,
                action_if_exists=wbi_enums.ActionIfExists.MERGE_REFS_OR_APPEND,
            )
            try:
                media.write(summary=wiki_edit_summary)
                tqdm.write(
                    f"No errors when trying to update {file_name} with SDC data."
                )
            except Exception as e:
                logging.error(f"Failed to write SDC for {file_name}: {e}")
        else:
            logging.info(f"No SDC data to add for {file_name}, skipping...")


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

    SKIP_CREATOR = config["SKIP_CREATOR"]
    INFER_BHL_PAGE_FROM_FLICKR_ID = config["INFER_BHL_PAGE_FROM_FLICKR_ID"]
    INFER_FROM_INTERNET_ARCHIVE = config["INFER_FROM_INTERNET_ARCHIVE"]
    INTERNET_ARCHIVE_OFFSET = config["INTERNET_ARCHIVE_OFFSET"]
    REF_URL_FOR_AUTHORS = config["REF_URL_FOR_AUTHORS"]
    COMMONS_API_ENDPOINT = config["COMMONS_API_ENDPOINT"]
    WIKIDATA_SPARQL_ENDPOINT = config["WIKIDATA_SPARQL_ENDPOINT"]
    BHL_BASE_URL = config["BHL_BASE_URL"]

    if args.category_raw:
        CATEGORY_RAW = args.category_raw
        config["CATEGORY_RAW"] = CATEGORY_RAW
    else:
        CATEGORY_RAW = config["CATEGORY_RAW"]

    CATEGORY_NAME = CATEGORY_RAW.replace("_", " ").replace("Category:", "").strip()

    output_file = DATA / f"{CATEGORY_NAME.replace(' ', '_')}.tsv"

    upload_metadata_to_commons(output_file)
