from pathlib import Path


bleed_img_dir = Path("/path/to/dir/with/bleed/images/")
nonbleed_img_dir = Path("/path/to/dir/with/nonbleed/images/")

cardback_dir = Path("/path/to/dir/with/cardbacks/")

RUNNER_CARDBACK_BLEED = cardback_dir / "runner_cb.jpg"
CORP_CARDBACK_BLEED = cardback_dir / "corp_cb.jpg"
RUNNER_CARDBACK_NONBLEED = cardback_dir / "runner_cb.jpg"
CORP_CARDBACK_NONBLEED = cardback_dir / "corp_cb.jpg"
reboot_change_yaml_path = "reboot_changes.yaml"
