export CATEGORY_RAW="Animalia_nova_sive_species_novae_testudinum_et_ranarum"

python3 get_metadata.py --auto_mode --category_raw "$CATEGORY_RAW"
python3 upload.py --auto_mode --category_raw "$CATEGORY_RAW"