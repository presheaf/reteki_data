import json

import glob
from pathlib import Path
from itertools import chain
import edn_format

code_dict = {}
out_dict = {}
edn_kw = edn_format.Keyword
for path in map(
    Path, chain(
        glob.glob("/home/karlerik/hobby/netrunner-data/edn/set-cards/*.edn"),
        glob.glob("/home/karlerik/hobby/netrunner_data_main/edn/set-cards/*.edn") # we want this to go last so old cards keep their old codes
    )

):
    with open(path) as f:
        cards = edn_format.edn_parse.parse_all(f.read())[0]
        for card in cards:
            card_id = card[edn_kw("card-id")]
            card_code = card[edn_kw("code")]
            if ("netrunner_data_main") in str(path) and card_code[0] in ["2", "3"] and card_id in code_dict:
                # skip revised core printings of old cards
                continue
            code_dict[card_id] = card_code
            out_dict[card_code] = {'flavor': card.get(edn_kw("flavor"))}
            try:
                illustrator = card[edn_kw("illustrator")]
                out_dict[card_code]["illustrator"] = illustrator
            except KeyError:
                print(f"{card_code} card {card[edn_kw('card-id')]}  in {path.stem} has no illustrator")

with open('card_illustrator_dict.json', 'w') as f:
    json.dump(out_dict, f)



with open('code_dict.json', 'w') as f:
    json.dump(code_dict, f)


