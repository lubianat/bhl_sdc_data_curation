# Biodiversity Heritage Library - Structured Data on Commons Data Curation

This repository hosts the code for parsing and updating Structured Data for the files from the Biodiversity Heritage Library on Wikimedia Commons. 

It relies on a custom WikibaseIntegrator patch available at https://github.com/lubianat/WikibaseIntegrator. 

It abides by the metadata model at https://docs.google.com/spreadsheets/d/1ocqDQBFaKAQvPsP3HMlrh52faiHiaDU-D9P3yz1oV_M/edit?gid=0#gid=0.

## Resources used

The script combines custom curation with calls to the Commons API, to the BHL website and to the Flickr API. 

## How to set up

Setting up the script for running is not as trivial as one may expect. 

The BHL collection on Commons is complex and adding new metadata in automated ways has several slippery slopes. 

That said, while curating metadata as a Wikimedian-in-Residence, I have adapted the code to consider many of such decisions.

### Watch out for

The script may perform poorly on:

- Categories with multiple cropped images, specially those cropped outside of Wikimedia Commons

- Categories with multiple kinds of images (text pages, maps, foldouts, drawings, photos etc)


### Pre-requisites

You will need:

- A Wikimedia account
- A BHL API key
- A Flickr API key 

You may set these as system variables or even hardcode then in a login.py file. 
Make sure these keys don't leak, e.g. when publishing the code on an online repository! 

login.py may look like:

USERNAME = "your-user-name"       
PASSWORD =  "your-password"
FLICKR_API_KEY= "the-flickr-key"
FLICKR_API_SECRET = "the-flickr-secret"
BHL_API_KEY = "the-bhl-api-key"


### Preparing the environment

I recommend strongly using a virtual environment, e.g. [venv](https://docs.python.org/3/library/venv.html).

Some of the dependencies, in particular WikibaseIntegrator, are mods from the versions in PyPi. 

You can assure you are installing the correct version by running `pip install -r requirements.txt` .


### Running the pipeline without manual curation 

While the script allows for adding some information manually, it implements many heuristics for better automation, relying particularly on Flickr tags. 

If you want to run the script for a particular Commons Category that includes BHL images, you may run:

```
cd src
bash auto_mode.sh
```

Then, the auto_mode will prompt you to add the category and upload the data. 

Of note, as of March 2025, the ability to revert editgroups on Commons is off, so make sure the batch is reliable before proceeding. 

Remember: on Linux, you may use Ctrl+S to pause the processing and Ctrl+Q to resume.