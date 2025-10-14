import sys
import pathlib
import edn_format
import subprocess
import os

from edn_format.edn_lex import Keyword

"""Helper script for traversing an image directory and replacing all images by proxied copies."""


sets_to_proxy = {
    'core',
    'revised-core',
    'system-core-2019',
    'genesis',
    'creation-and-control',
    'spin',
    'honor-and-profit',
    'lunar',
    'order-and-chaos'
}

raw_data_edn_path = sys.argv[1]
image_dir = sys.argv[2]
edn_dir = sys.argv[3]
proxygen_path = sys.argv[4]
tmp_path = 'tmp.edn'

with open(raw_data_edn_path) as f:
    cards = edn_format.edn_parse.parse(f.read())[Keyword('cards')]

for card_dict in cards:
    if card_dict[Keyword('cycle_code')] not in sets_to_proxy:
        continue

    code = str(card_dict[Keyword('code')])
    edn_path = str(pathlib.Path(edn_dir) / (card_dict[Keyword('normalizedtitle')] + '.edn'))
    img_path = pathlib.Path(image_dir) / f'{code}.png'

    print(f'Generating {code}')
    if not subprocess.run(['python3', proxygen_path, edn_path, str(img_path), str(img_path)]):
        print(f'Error generating {code}')

    for prev_code in map(str, card_dict.get(Keyword('previous-versions'), [])):
        print(f'Copying {code} to {prev_code}')
        other_img_path = pathlib.Path(image_dir) / f'{prev_code}.png'
        other_img_path.write_bytes(img_path.read_bytes())
