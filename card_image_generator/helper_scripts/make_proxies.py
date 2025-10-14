import itertools
import json
import yaml
import subprocess
from pathlib import Path
from multiprocessing import Pool

BLEED_SCRIPT = '/home/karlerik/hobby/proxynexus/misc/border_generator_cv.py'

POST_MIDLUNAR_RESOURCE_CARD_CODES: list[str] = [
    '06080',
    '06097',
    '06100',
    '06120',
    '07048',
    '07049',
    '07050',
    '07051',
    '07052',
    '07055',
    '08002',
    '08003',
    '08005',
    '08006',
    '08007',
    '08009',
    '08022',
    '08029',
    '08030',
    '08031',
    '08044',
    '08062',
    '08067',
    '08068',
    '08082',
    '08083',
    '08084',
    '08085',
    '08086',
    '08087',
    '08103',
    '08108',
    '09035',
    '09036',
    '09041',
    '09042',
    '09043',
    '09044',
    '09051',
    '09052',
    '09055',
    # '07004'                     # Firmware Updates - doesn't actually belong here!
]

PRE_MIDLUNAR_RESOURCES = [
    '01015',
    '01016',
    '01029',
    '01030',
    '01031',
    '01032',
    '01047',
    '01048',
    '01052',
    '01053',
    '02008',
    '02022',
    '02025',
    '02042',
    '02049',
    '02050',
    '02063',
    '02067',
    '02068',
    '02069',
    '02082',
    '02091',
    '02103',
    '02105',
    '02109',
    '03049',
    '03050',
    '03051',
    '03053',
    '03054',
    '03055',
    '04008',
    '04009',
    '04023',
    '04046',
    '04048',
    '04049',
    '04062',
    '04069',
    '04083',
    '04106',
    '05048',
    '05049',
    '05050',
    '05054',
    '05055',
    '06016',
    '06020',
    '06040',
    '06054',
    '06056',
    '06058',
    '06059',
    '06060',
    '06075'
]

# SKIPPED_CHANGES = [
#     "02079",
#     "04043",
#     "05017",
#     "05020",
#     "06019",
#     "06027",
#     "08115",
#     "08117"
# ]
IDENTITY_CARDS = ['01001', '01017', '01033', '02001', '02046', '02083', '03028', '03029', '03030', '04041', '05028', '05029', '05030', '06017', '06052', '06095', '07028', '07029', '07030', '08025', '08063', '08104', '09029', '09037', '09045']

TMP_LIST = [
    # quote stuff
    "01023",
    "01036",
    "01049",
    "01096",
    "01103",
    "01104",
    "01108",
    "01110",
    "02008",
    "02054",
    "02056",
    "02072",
    "02082",
    "02089",
    "03033",
    "04006",
    "04008",
    "04020",
    "04032",
    "04049",
    "04067",
    "04068",
    "04093",
    "04104",
    "04108",
    "06016",
    "06019",
    "06073",
    "06075",
    "06080",
    "06081",
    "06099",
    "06113",
    "07008",
    "07018",
    "07025",
    "07048",
    "07050",
    "08016",
    "08019",
    "08030",
    "08052",
    "08057",
    "08107",
    "09026",
]

SPECIAL_CASES: dict[str, dict[str, str]] = {
    '08012': {
        'faces/biotech-front.edn': '08012_front',
        'faces/biotech-brewery.edn': '08012_back_1',
        'faces/biotech-greenhouse.edn': '08012_back_2',
        'faces/biotech-tank.edn': '08012_back_3'
    },

    '09001': {
        'faces/sync-front.edn': '09001_front',
        'faces/sync-back.edn': '09001_back',
    }
}

# BLEED = "bleeds"
# UNBLEED = "imgs"


# Note: making these _without_ the post-lunar templates, so those need to be remade after!
outdir_root = Path("outdir/fullset_240323_quotes/")
outdir_unchanged = outdir_root / "unchanged"
outdir_db_changed = outdir_root / "changed_deckbuilding"
outdir_changed = outdir_root / "changed"
BLEED = "bleeds"
UNBLEED = "nonbleeds"


def should_print(card_code: str):

    # # TMP fix
    # if card_data['ingame_change'] or card_data['change'] is None:
    #     return False

    return card_code in TMP_LIST
    return card_code[:2] in {
        "01",                   # core
        "02",                   # genesis
        "03",                   # C&C
        "04",                   # spin
        "05",                   # H&P
        "06",                   # lunar
        "07",                   # O&C
        "08",                   # sansan
        "09",                   # D&D
        # "10",                   # Mumbad
        # "11",                   # Flashpoint
        # "12",                   # Red Sands
    } # and card_code in PRE_MIDLUNAR_RESOURCES

    # return card_code in SKIPPED_CHANGES
    # return 9028 < int(card_code) < 9053


def card_code_worker(card_code: tuple[str, dict]):
    code, data = card_code
    if not should_print(code):
        return

    outdir = outdir_changed if data["ingame_change"] else outdir_db_changed if data["change"] else outdir_unchanged

    # TODO: quick and dirty merge here - might want to double check
    card = data["id"]
    # check_output ensures crash on error
    if code in SPECIAL_CASES:
        edn_paths, proxy_paths = [], []
        for k, v in SPECIAL_CASES[code].items():
            edn_paths.append(f"../edn/{k}")
            proxy_paths.append(str((outdir / UNBLEED) / f"{v}.png"))

    else:
        proxy_paths = [str((outdir / UNBLEED) / f"{code}.png")]
        edn_paths = [f"../edn/cards/{card}.edn"]

    for edn_path, proxy_path in zip(edn_paths, proxy_paths):
        print(f'Generating {code=} ({card=}) to {outdir}...')
        subprocess.check_output(["python", "proxygen.py", edn_path, proxy_path])
        subprocess.check_output(["python", BLEED_SCRIPT, proxy_path, '-o', str(outdir / BLEED)])


if __name__ == '__main__':
    card_change_dict = yaml.safe_load(Path(
        '/home/karlerik/hobby/netrunner-data/reboot_changes.yaml'
    ).read_text())

    code_dict = json.loads(
        Path("/home/karlerik/hobby/netrunner-data/code_dict.json").read_text()
    )

    for d in [outdir_changed, outdir_unchanged, outdir_db_changed]:
        d.mkdir(exist_ok=True, parents=True)

    for d, sd in itertools.product([outdir_changed, outdir_unchanged, outdir_db_changed], [BLEED, UNBLEED]):
        (d / sd).mkdir(exist_ok=True, parents=True)

    # sort is to ensure cards are generated in order and changed cards come first

    all_things = sorted(card_change_dict.items(),
                        key=lambda tpl: (-int(tpl[1]['ingame_change']), tpl[1]['change'] is None))
    with Pool(8) as p:
        p.map(card_code_worker, all_things)
