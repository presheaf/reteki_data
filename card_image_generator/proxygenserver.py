from enum import Enum
from io import BytesIO

from flask import Flask, make_response, render_template, request
from PIL import Image
from proxygen import make_card_proxy
from werkzeug.middleware.proxy_fix import ProxyFix


app = Flask(__name__)

# Limit size of file uploads to 16MB

app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000

# Assumes we are behind reverse-proxy - otherwise comment this out
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


class Faction(str, Enum):
    NBN = "nbn"
    WEYLAND = "weyland-consortium"
    HB = "haas-bioroid"
    JINTEKI = "jinteki"
    NEUTRAL_CORP = "neutral-corp"
    CRIMINAL = "criminal"
    ANARCH = "anarch"
    SHAPER = "shaper"
    NEUTRAL_RUNNER = "neutral-runner"
    ADAM = "adam"
    APEX = "apex"
    SUNNY = "sunny-lebeau"


FACTION_NAMES = [f.value for f in Faction]
CORP_FACTIONS = [
    Faction.NBN,
    Faction.WEYLAND,
    Faction.HB,
    Faction.JINTEKI,
    Faction.NEUTRAL_CORP,
]
RUNNER_FACTIONS = [f for f in Faction if f not in CORP_FACTIONS]
NON_ID_FACTIONS = [
    Faction.NEUTRAL_CORP,
    Faction.NEUTRAL_RUNNER,
    Faction.ADAM,
    Faction.APEX,
    Faction.SUNNY,
]


@app.route("/")
def cardgen_form():
    return render_template("cardgen-form.html")


def validate_and_remap(card_dict: dict) -> dict:
    card_type = card_dict.get("type")
    assert card_type, "Cards must have a type!"
    if "uniqueness" not in card_dict and card_type != "identity":
        card_dict["uniqueness"] = False

    card_faction = card_dict.get("faction")
    assert card_faction in FACTION_NAMES, f"Can't make card type {card_type} for faction {card_faction}!"

    side = "corp" if card_faction in CORP_FACTIONS else "runner"

    assert not (
        card_type == "identity" and card_faction in NON_ID_FACTIONS
    ), f"No ID template for {card_faction}"

    required_keys = {
        "title",
        "cost-or-advancement-req-or-decksize",
        "type",
        "title",
        "faction"
    }

    admissible_keys = {
        "uniqueness",
        "text",
        "flavor",
        "subtype",
        "illustrator",
        "bg-image",
        "influence-cost",
        "font-scaling-factor",
        "full-art"
    }

    if card_type == "ice":
        required_keys.add("strength-or-pts-or-inflimit")
        # admissible_keys.add("trash-cost")
    elif card_type == "identity":
        admissible_keys.remove("influence-cost")
        required_keys.add("strength-or-pts-or-inflimit")
        if side == "runner":
            required_keys.add("memory-cost-or-base-link")

    elif card_type == "agenda":
        required_keys.add("strength-or-pts-or-inflimit")
        if card_faction != Faction.NEUTRAL_CORP:
            admissible_keys.remove("influence-cost")
    elif card_type in {"asset", "upgrade"}:
        required_keys.add("trash-cost")
    elif card_type in "operation":
        # admissible_keys.add("trash-cost")
        pass
    elif card_type == "program":
        required_keys.add("memory-cost-or-base-link")
        admissible_keys.add("strength-or-pts-or-inflimit")
    elif card_type in {"hardware", "resource", "event"}:
        pass

    admissible_keys |= required_keys
    assert set(card_dict.keys()).issubset(admissible_keys | required_keys), (
        f"Found inadmissible keys for {card_type} cards: " + ', '.join(
            set(card_dict.keys()).difference(admissible_keys)
        )
    )
    assert set(required_keys).issubset(card_dict.keys()), (
        f"Required keys for {card_type} cards not found: " + ', '.join(
            required_keys.difference(set(card_dict.keys()))
        )
    )

    if side == "corp":
        assert card_type in [
            "agenda",
            "ice",
            "upgrade",
            "asset",
            "operation",
            "identity",
        ], f"{card_dict['type']} is not a Corp card type"
    else:
        assert card_type in [
            "program",
            "hardware",
            "resource",
            "event",
            "identity",
        ], f"{card_dict['type']} is not a Runner card type"

    # hack to avoid having to fix my code, which assumes ice always has a subtype
    if card_type == "ice" and not card_dict.get("subtype"):
        card_dict["subtype"] = " "
    assert not (
        card_type == "identity" and card_dict["title"].count(": ") != 1
    ), "Identities must have a title of the form 'A: B', e.g. 'NBN: Making News'"

    # do some remapping
    if "strength-or-pts-or-inflimit" in card_dict:
        if card_type == "agenda":
            new_key = "agenda-points"
        elif card_type == "identity":
            new_key = "influence-limit"
        else:
            new_key = "strength"
        card_dict[new_key] = card_dict.pop("strength-or-pts-or-inflimit")

    if "cost-or-advancement-req-or-decksize" in card_dict:
        # probably always, right?
        if card_type == "agenda":
            new_key = "advancement-requirement"
        elif card_type == "identity":
            new_key = "minimum-deck-size"
        else:
            new_key = "cost"
        card_dict[new_key] = card_dict.pop("cost-or-advancement-req-or-decksize")

    if "memory-cost-or-base-link" in card_dict:
        # probably always, right?
        if card_type == "identity":
            new_key = "base-link"
        elif card_type == "program":
            new_key = "memory-cost"
        card_dict[new_key] = card_dict.pop("memory-cost-or-base-link")

    return card_dict


@app.route("/", methods=["POST"])
def my_form_post():

    card_dict = {}
    for k in request.form:
        if request.form.get(k):
            card_dict[k] = request.form[k]

    if "bg-image" in request.files and request.files["bg-image"].filename:
        # receive the file
        buf = BytesIO()
        request.files["bg-image"].save(buf)
        try:
            bg_image = Image.open(buf)
        except Exception:
            return "Error opening image!", 400
    else:
        bg_image = None

    try:
        card_dict = validate_and_remap(card_dict)
    except AssertionError as e:
        return str(e), 400
    try:
        card_dict["influence-cost"] = int(card_dict.get("influence-cost", 0))
    except ValueError:
        return f"Invalid influence cost {card_dict.get('influence-cost')}", 400

    if card_dict.get("subtype"):
        card_dict["subtype"] = card_dict["subtype"].split(",")

    if "illustrator" in card_dict:
        card_dict["illustrator"] = f'Illus.: {card_dict["illustrator"]}'

    font_scaling_factor = float(request.form.get("font-scaling-factor", "1.0"))
    make_full_art = request.form.get("full-art")
    card_img = make_card_proxy(card_dict, None, fudge_factor=font_scaling_factor, make_alt=make_full_art)
    out_buf = BytesIO()
    newsize = tuple(map(lambda x: round(0.7 * x), card_img.size))
    card_img = card_img.resize(newsize).convert("RGBA")

    if bg_image:
        bg_image = bg_image.resize(card_img.size).convert("RGBA")
        bg_image.paste(card_img, mask=card_img)
        card_img = bg_image

    card_img.convert("RGB").save(out_buf, format="jpeg", quality=85)
    img_bytes = out_buf.getvalue()

    response = make_response(img_bytes)
    response.headers["Content-Type"] = "image/jpeg"
    return response, 200
