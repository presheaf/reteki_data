import functools
import itertools
import json
import subprocess
import tempfile
from pathlib import Path
from pprint import pprint

import edn_format
import matplotlib
import randimage
import yaml
import pickle
from proxygen_utils import card_dict_from_edn_text, dict_pyfy, pyfy



# Given a set, iterate over it and find all the card codes. For each card code, first attempt to generate it. If it works, the card was an old card, so do nothing. If not, check the faces dir - if there is cardid-front/back there, there are two faces, and generate each one. Otherwise, check a given art dir and use the image there if possible, otherwise just use black (someday, autogenerate?)

# Store outputs as cardcode.jpg, or cardcode-{front,back}.jpg


OLD_NR_DATA_DIR = Path("/home/karlerik/hobby/netrunner-data/")
NR_DATA_DIR = Path("/home/karlerik/hobby/reteki_data/")
EDN_DIR = NR_DATA_DIR / "edn/cards/"
FACES_DIR = NR_DATA_DIR / "edn/faces/"
BG_IMG_DIR = OLD_NR_DATA_DIR / "new_cards/pretexts/"
AUTOGEN_BG_IMG_PICKLE = OLD_NR_DATA_DIR / "new_cards/pretexts/generated.pkl"
PROXYGEN_PATH = NR_DATA_DIR / "card_image_generator/proxygen.py"

SET_EDN_PATH = NR_DATA_DIR / "edn/set-cards/new-normal.edn"
OUTPUT_PATH = NR_DATA_DIR / "scratch/limit-cycle-1/251230/"

OUTPUT_PATH.mkdir(exist_ok=True)
try:
    with open(AUTOGEN_BG_IMG_PICKLE, 'rb') as f:
        autogen_imgs = pickle.load(f)
        assert isinstance(autogen_imgs, dict)
except FileNotFoundError:
    autogen_imgs = {}

@functools.lru_cache()
def make_random_image(card_id):
    # Image generation takes a while, so cache for simplicity
    if card_id not in autogen_imgs:
        autogen_imgs[card_id] = randimage.get_random_image((344, 480))
    return autogen_imgs[card_id]

with open(SET_EDN_PATH) as f:
    edn_list = edn_format.edn_parse.parse(f.read())
    card_dict_list = [dict_pyfy(d) for d in edn_list]


for card_dict in card_dict_list:
    card_code, card_id = card_dict["code"], card_dict["card-id"]
    special_cards_list = {
        "53031": {"consolidation": "53031"},
        "51015": {"the-horde-front": "51015_front", "the-horde-back": "51015_back"},
        "51027": {"repurpose_flavor": "51027"}}
    if direct_copies := special_cards_list.get(card_code):
        for src_path, dst_path in direct_copies.items():
            # wouldn't you know it, this doesn't need to be generated!
            print(f"  Just copying {src_path}")
            card_img_path = BG_IMG_DIR / f"{src_path}.jpg"
            (OUTPUT_PATH / f"{dst_path}.jpg").write_bytes(card_img_path.read_bytes())
        continue
    try:
        # If it's an existing card, background is autodected
        subprocess.check_output(
            [
                "python",
                PROXYGEN_PATH,
                EDN_DIR / f"{card_id}.edn",
                OUTPUT_PATH / f"{card_code}.jpg",
            ]
        )
        print(f"Generated rebooted card {card_code} ({card_id})!")

    except subprocess.CalledProcessError:
        # Otherwise, we make a random one - just check if there are two faces first

        if (FACES_DIR / f"{card_id}-front.edn").exists():
            to_generate = [
                (
                    FACES_DIR / f"{card_id}-{side}.edn",
                    OUTPUT_PATH / f"{card_code}_{side}.jpg",
                )
                for side in ["front", "back"]
            ]
        else:
            to_generate = [
                (EDN_DIR / f"{card_id}.edn", OUTPUT_PATH / f"{card_code}.jpg")
            ]

        for edn_path, proxy_path in to_generate:
            with tempfile.NamedTemporaryFile(suffix=".jpg") as tmpf:

                if (BG_IMG_DIR / f"{edn_path.stem}.jpg").exists():
                    bg_path = str(BG_IMG_DIR / f"{edn_path.stem}.jpg")
                    print(f"Already got art for card {card_code} ({card_id})")
                else:
                    print(f"Generating art for card  {card_code} ({card_id})")
                    matplotlib.image.imsave(tmpf.name, make_random_image(str(edn_path)))
                    bg_path = tmpf.name
                try:
                    subprocess.check_output(
                        ["python", PROXYGEN_PATH, edn_path, proxy_path, bg_path]
                    )
                except subprocess.CalledProcessError as e:
                    print(e)

with open(AUTOGEN_BG_IMG_PICKLE, 'wb') as f:
    print("Pickling playtest imgs")
    pickle.dump(autogen_imgs, f)
