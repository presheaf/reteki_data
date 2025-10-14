import json
import sys
from os import symlink
from pathlib import Path

dir_to_work = sys.argv[1]
if not Path(dir_to_work).exists():
    print(f"Dir {dir_to_work} doesn't exist!")
    sys.exit(1)

json_dict_path = sys.argv[2]
try:
    with open(json_dict_path) as f:
        card_code_dict = json.load(f)
except Exception as e:
    print(f"Failed to load JSON dict from {json_dict_path}: {str(e)}")
    sys.exit(1)

suffix = "jpg" if len(sys.argv) < 3 else sys.argv[3]

for print_code, orig_code in card_code_dict.items():
    card_path = Path(dir_to_work) / f"{print_code}.{suffix}"

    orig_path = Path(dir_to_work) / f"{card_code_dict[print_code]}.{suffix}"
    if card_path == orig_path:
        # no linking needed
        continue
    try:
        symlink(orig_path, card_path)
        print(f"Made link {card_path} -> {orig_path}")
    except FileExistsError:
        print(f"Skipping {card_path} because it exists")
