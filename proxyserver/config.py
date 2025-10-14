from pathlib import Path


bleed_img_dir = Path(
    "/home/karlerik/hobby/reboot_card_images"
)
nonbleed_img_dir = Path(
    "/home/karlerik/hobby/reboot_card_images/"
)

cardback_dir = Path("/home/karlerik/hobby/netrunner-data/proxyserver")

RUNNER_CARDBACK_BLEED = cardback_dir / "runner_cb.jpg"
CORP_CARDBACK_BLEED = cardback_dir / "corp_cb.jpg"
RUNNER_CARDBACK_NONBLEED = cardback_dir / "runner_cb.jpg"
CORP_CARDBACK_NONBLEED = cardback_dir / "corp_cb.jpg"

reboot_change_yaml_path = "reboot_changes.yaml"
alts_yaml_path = "alts.yaml"
