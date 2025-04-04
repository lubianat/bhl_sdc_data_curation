# Ask the user for the category raw input 
echo "Enter the Wikimedia Commons category input: "
read CATEGORY_RAW

python3 get_metadata.py --auto_mode --category_raw "$CATEGORY_RAW"
python3 upload.py --auto_mode --category_raw "$CATEGORY_RAW"