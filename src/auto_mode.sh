export CATEGORY_RAW="A flora of North America"

python3 get_metadata.py --auto_mode --category_raw "$CATEGORY_RAW"
python3 upload.py --auto_mode --category_raw "$CATEGORY_RAW"