import json

import glob
from pathlib import Path

import edn_format
import yaml
from collections import defaultdict
code_dict = defaultdict(list)
title_dict = dict()

edn_kw = edn_format.Keyword
for path in map(
    Path, glob.glob("/home/karlerik/hobby/netrunner-data/edn/set-cards/*.edn")
):
    with open(path) as f:
        cards = edn_format.edn_parse.parse_all(f.read())[0]
        for card in cards:
            card_id = card[edn_kw("card-id")]
            code_dict[card_id].append(card[edn_kw("code")])

            card_data_path = Path("/home/karlerik/hobby/netrunner-data/edn/cards/") / f'{card_id}.edn'
            card_data = edn_format.edn_parse.parse_all(card_data_path.read_bytes())[0]
            title_dict[card_id] = card_data[edn_kw("title")]


multi_print_dict = {}

with open('changed_cards.yaml') as f:
    changed_ids = yaml.safe_load(f)

for k in list(code_dict):
    earliest_print_code = min(code_dict[k])
    if len(code_dict[k]) > 1:
        for printing in code_dict[k]:
            multi_print_dict[printing] = earliest_print_code

    code_dict[k] = earliest_print_code
    if int(code_dict[k][:2]) > 12 and int(code_dict[k][:2]) < 50: # TD or later, or not a booster card
        del code_dict[k]


output_dict = {'titles_to_codes': {}, 'changed_titles': []}
for card_id in sorted(code_dict, key=lambda k: code_dict[k]):
    card_title = title_dict[card_id]
    output_dict['titles_to_codes'][card_title] = code_dict[card_id]
    if card_id in changed_ids:
        output_dict['changed_titles'].append(card_title)

with open("changed_card_titles.json", "w") as f:
    json.dump(output_dict, f)
with open("card_printing_codes.json", "w") as f:
    json.dump(multi_print_dict, f)

with open("changed_card_codes.json", "w") as f:
    json.dump([code_dict[card_id] for card_id in changed_ids if code_dict[card_id]], f)

with open("code_dict.json", "w") as f:
    json.dump(code_dict, f)


# # Path('/home/karlerik/hobby/netrunner-data/flavor_dict.yaml').write_text(yaml.dump(flavor_dict))
# known_charset = "\n !\"#$%&\'()*+,-./0123456789:;<=>?ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]abcdefghijklmnopqrstuvwxyz"
# # \xa0: ignorable
# known_charset += "…ō—é\xa0àēǒ₂↑™ñū"

# known_charset += "δὶς ἐς τὸν αὐτὸν ποταμὸν οὐκ ἂν ἐμβαίηΔεν υπἁρχει τίποτα μόνιμο, εκτός από την αλλαγή.Μεγάλο μέρος της μάθησης δεν διδάσκει την κατανόηση"

# for code, f in flavor_dict.items():
#     l = [(i, c) for i, c in enumerate(f) if c not in known_charset]
#     if l:
#         print(l)
#         print(f'{code} {repr(f)}')
#         break


# # charset = ''.join(sorted({c for flavor in flavor_dict.values() for c in flavor}))
