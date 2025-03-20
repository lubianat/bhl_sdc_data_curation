export CATEGORY_RAW="Traité élémentaire et complet d'ornithologie, ou, Histoire naturelle des oiseaux"

python3 get_metadata.py --auto_mode --category_raw "$CATEGORY_RAW"
python3 upload.py --auto_mode --category_raw "$CATEGORY_RAW"