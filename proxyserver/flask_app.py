import itertools
import random
import zipfile
from collections import defaultdict
from io import BytesIO
from math import floor
from pathlib import Path
from typing import Optional, Literal

import PIL
from flask import Flask, escape, make_response, render_template, request
from fpdf import FPDF
from proxy_data import (CORP_CARDBACK_BLEED, CORP_CARDBACK_NONBLEED,
                        RUNNER_CARDBACK_BLEED, RUNNER_CARDBACK_NONBLEED,
                        ChangeLevel, bleed_img_dir, card_change_levels,
                        card_change_strings, nonbleed_img_dir,
                        cardname_to_img_basename, cardname_to_alts_basename, multi_faced_cards, cardname_aliases)
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

# Assumes we are behind reverse-proxy - otherwise comment this out
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

all_cardnames = set(cardname_to_img_basename.keys())


@app.route("/")
def decklist_form():
    return render_template("decklist-form.html")


@app.route("/full_set_explanation")
def google_drive_explanation_page():
    return render_template("full-set-explanation.html")


def case_insensitive_substring_lookup(key: str, stringset: set[str]) -> tuple[str, ...]:
    if key in stringset:
        return (key,)
    return tuple({s for s in stringset if key.lower() in s.lower()})


def process_user_input(user_input) -> tuple[dict[str, int], list[str]]:
    """Return a dict of the cards we did understand and a list of the ones we didn't."""

    deck: dict[str, int] = defaultdict(lambda: 0)
    confusing_lines = []
    for line in user_input.split("\n"):
        line = line.strip()
        if not line:  # skip newlines
            continue
        try:
            if not line[0].isnumeric():
                num = 1
                cardname = line
            else:
                num, *cardname = line.split(" ")
                cardname = " ".join(cardname).strip()
                num = int(num)

            assert num >= 0
            if cardname.lower() in cardname_aliases:
                cardname = cardname_aliases[cardname.lower()]
            else:
                matching_cardnames = case_insensitive_substring_lookup(cardname, all_cardnames)
                if len(matching_cardnames) > 1:
                    err_msg = f"Ambiguous - matches {matching_cardnames}"
                elif len(matching_cardnames) == 0:
                    err_msg = "No matching cards found - check your spelling"
                else:
                    err_msg = ""  # won't be displayed
                assert len(matching_cardnames) == 1, err_msg
                cardname = matching_cardnames[0]

            assert cardname is not None
            deck[cardname] += num
        except (ValueError, AssertionError) as e:
            if isinstance(e, AssertionError):
                line += f" ({e})"
            confusing_lines.append(line)

    return dict(deck), confusing_lines


def cardnames_to_img_paths(
        deck: dict[str, int], minimum_change_level: ChangeLevel, include_bleeds: bool, use_full_arts: bool
) -> list[tuple[str, ...]]:
    """Filter out cardnames which are unchanged, and return a big list of images to put in the pdf.
    Each entry is either (img_path,) for regular cards, or (face_1_img_path, face_2_img_path, ...)
    for cards which need an image also on the reverse side."""

    changed_deck = {
        cardname: num
        for cardname, num in deck.items()
        if card_change_levels[cardname] >= minimum_change_level  # type: ignore
    }

    img_dir = (bleed_img_dir if include_bleeds else nonbleed_img_dir)
    img_paths = []

    for cardname, num in changed_deck.items():
        _facenames = multi_faced_cards.get(cardname, (cardname,))
        _face_img_paths = []
        for _facename in _facenames:
            if (not use_full_arts or (cardname not in cardname_to_alts_basename)):
                _face_img_paths.append(str(img_dir / (cardname_to_img_basename[_facename])))
            else:
                _face_img_paths.append(str(img_dir / cardname_to_alts_basename[_facename]))
        for _ in range(num):
            img_paths.append(tuple(_face_img_paths))

    return img_paths


def imgs_to_pdf(img_paths: list[str], is_bleeds: bool, paper_type: Literal["A4", "Letter", "Legal"]) -> bytes:
    paper_width_mm, paper_height_mm = {"A4": (210, 297),
                                       "Letter": (216, 279),
                                       "Legal":  (216, 356)}.get(paper_type)
    pdf = FPDF("P", "mm", paper_type)  # P = portrait

    nonbleed_width_mm = 62
    nonbleed_height_mm = 88
    bleed_width_mm = 67  # 68 more accurate, i think
    bleed_height_mm = 93

    bleed_margin_w_mm = (bleed_width_mm - nonbleed_width_mm) / 2
    bleed_margin_h_mm = (bleed_height_mm - nonbleed_height_mm) / 2

    card_width_mm = bleed_width_mm if is_bleeds else nonbleed_width_mm
    card_height_mm = bleed_height_mm if is_bleeds else nonbleed_height_mm

    w_margin = round(floor((paper_width_mm - 3 * card_width_mm) / 4))
    h_margin = round(floor((paper_height_mm - 3 * card_height_mm) / 4))

    page_layout = [
        (
            w_margin * (i + 1) + card_width_mm * i,
            h_margin * (j + 1) + card_height_mm * j,
        )
        for i in range(3)
        for j in range(3)
    ]
    page_size = len(page_layout)

    # split the images into pages
    batches = []
    while len(img_paths) >= page_size:
        batch, img_paths = img_paths[:page_size], img_paths[page_size:]
        batches.append(batch)

    if img_paths:
        batches.append(img_paths)

    # put everything onto the pages
    for batch in batches:
        pdf.add_page()

        # paste the imgs
        for img, pos in zip(batch, page_layout):
            pdf.image(img, x=pos[0], y=pos[1], w=card_width_mm, h=card_height_mm)

        # maybe draw lines
        if is_bleeds:
            for i in range(3):
                eps = 0.02
                pdf.set_draw_color(125, 125, 125)
                pdf.set_line_width(0.00000001)

                # horizontal lines around row i
                H = (i + 1) * h_margin + i * bleed_height_mm + bleed_margin_h_mm
                pdf.dashed_line(0, H - eps, paper_width_mm, H - eps)
                pdf.dashed_line(
                    0,
                    H + nonbleed_height_mm + eps,
                    paper_width_mm,
                    H + nonbleed_height_mm + eps,
                )

                # vertical lines around column i
                W = (i + 1) * w_margin + i * bleed_width_mm + bleed_margin_w_mm
                pdf.dashed_line(W - eps, 0, W - eps, paper_height_mm)
                pdf.dashed_line(
                    W + nonbleed_width_mm + eps,
                    0,
                    W + nonbleed_width_mm + eps,
                    paper_height_mm,
                )

    return pdf.output("", "S").encode("latin-1")


def watermark_jpg_corner(rng_seed: int, img_bytes: bytes, watermark_size_px=7) -> bytes:
    """Adds a small random watermark to the lower right corner of an image. Only tested with a couple
    PNG and JPGs, probably makes some assumption of image pixel access that some formats violates."""
    img = PIL.Image.open(BytesIO(img_bytes))
    pixels = img.load()

    random.seed(rng_seed)
    for i, j in itertools.product(range(watermark_size_px), range(watermark_size_px)):
        curr_pixel = pixels[-i, -j]
        # change the pixel at offset (i, j) from lower right corner to a random color, with
        # some hacky weighing to keep it close ish to what's there currently
        pixels[-i, -j] = tuple(
            random.randint(
                int(0.3 * curr_pixel[k]), min(255, 10 + int(1.5 * curr_pixel[k]))
            )
            for k in range(len(curr_pixel))
        )
    out_buf = BytesIO()
    img.save(out_buf, format=img.format, quality=97)
    return out_buf.getvalue()


def imgs_to_zip(card_img_paths: list[tuple[str, ...]], add_watermarks: bool) -> bytes:
    """Zip up a bunch of images into one big file."""

    zip_bytes = BytesIO()
    with zipfile.ZipFile(zip_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for card_idx, face_paths in enumerate(card_img_paths):
            for face_idx, img_path in enumerate(map(Path, face_paths)):
                img_bytes = img_path.read_bytes()
                if add_watermarks:
                    img_bytes = watermark_jpg_corner(card_idx, img_bytes)
                face_idx_str = "_front" if face_idx == 0 else f"_reverse_{face_idx}"
                zf.writestr(f"cards/{card_idx:0>4}{face_idx_str}{img_path.suffix}", img_bytes)

        for basename, path in (
            [
                ("runner_cardback_bleed", RUNNER_CARDBACK_BLEED),
                ("corp_cardback_bleed", CORP_CARDBACK_BLEED),
            ]
            if add_watermarks
            else [
                ("runner_cardback", RUNNER_CARDBACK_NONBLEED),
                ("corp_cardback", CORP_CARDBACK_NONBLEED),
            ]
        ):
            zf.writestr(
                f"cardbacks/{basename}{path.suffix}",
                path.read_bytes(),
            )

    return zip_bytes.getvalue()


def make_changelist(cardnames_to_proxy: dict[str, int], min_change_level) -> str:
    cardnames = {
        cardname
        for cardname in cardnames_to_proxy.keys()
        if card_change_levels[cardname] >= min_change_level
    }
    if not cardnames:
        return "---nothing to list---"

    max_cardname_len = max(len(cardname) for cardname in cardnames)
    return "\n".join(
        f"{cardname.ljust(max_cardname_len)}   {card_change_strings[cardname]}"
        for cardname in sorted(cardnames)
        if card_change_levels[cardname] >= min_change_level
    )


@app.route("/", methods=["POST"])
def my_form_post():
    text = request.form["decklist"]
    min_change_level = {
        "unchanged": ChangeLevel.Unchanged,
        "changed": ChangeLevel.DeckConstructionChange,
        "ingame-changed": ChangeLevel.IngameChange,
    }.get(request.form.get("min-change-level"), ChangeLevel.Unchanged)

    generate_type = request.form.get("generate-type")
    include_bleeds = request.form.get("include-bleeds")
    use_full_arts = request.form.get("use-full-arts")
    paper_type = request.form.get("paper-type")

    cardnames_to_proxy, incorrect_input = process_user_input(text)

    if incorrect_input:
        error_msg = (
            "<b>Error:</b> Failed to understand the following lines of input (Note:"
            + "Currently only Flashpoint and earlier cards are supported - please let me "
            + "know if you need others) : <p><p> "
            + "<br>".join(map(escape, incorrect_input))
            + "<p><p>Please fix or remove them and try again."
        )
        return error_msg, 400

    img_paths = cardnames_to_img_paths(
        cardnames_to_proxy, min_change_level, include_bleeds, use_full_arts
    )

    if len(img_paths) > 110 and generate_type != "txt":
        return f"Please only proxy 110 cards at a time (you had {len(img_paths)})", 413

    if generate_type == "pdf":
        flattened_img_paths = [_p for tpl in img_paths for _p in tpl]
        pdf_bytes = imgs_to_pdf(flattened_img_paths, include_bleeds, paper_type)
        response = make_response(pdf_bytes)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = "inline; filename=proxies.pdf"
        return response

    elif generate_type == "zip":
        zip_bytes = imgs_to_zip(img_paths, add_watermarks=include_bleeds)
        response = make_response(zip_bytes)
        response.headers["Content-Type"] = "application/zip"
        response.headers["Content-Disposition"] = "inline; filename=proxies.zip"
        return response

    else:  # making a changelist
        changelist = make_changelist(cardnames_to_proxy, min_change_level)
        response = make_response(changelist)
        response.headers["Content-Type"] = "text/plain"
        return response
