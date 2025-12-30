import json
import pathlib
import re
import sys
from enum import Enum
from pathlib import Path
from typing import NamedTuple, Optional

import edn_format
import yaml
from PIL import Image, ImageDraw, ImageFont

# flavor_dict = yaml.load(Path('/home/karlerik/hobby/netrunner-data/flavor_dict.yaml').read_text())

# Haven't bothered making a template for literally just 1 card
PREMADE_IDS = {
    "09029": "apex",  # apex ID
    "09037": "adam",  # adam ID
    "09045": "sunny",  # sunny ID
}

SPECIAL_FACES = {
    "biotech-front": ("08012", "special_images/biotech_front.jpg"),
    "biotech-greenhouse": ("08012", "special_images/biotech_greenhouse.jpg"),
    "biotech-brewery": ("08012", "special_images/biotech_brewery.jpg"),
    "biotech-tank": ("08012", "special_images/biotech_tank.jpg"),
    "sync-front": ("09001", "special_images/sync_front.jpg"),
    "sync-back": ("09001", "special_images/sync_back.jpg"),
}
SPLIT_AGENDA_RELPATHS = {
    "power-grid-reroute": "odd_cards/split_agendas/hb_weyland_agenda.png",
    "psychomagnetic-pulse": "odd_cards/split_agendas/hb_jinteki_agenda.png",
    "adaptive-netbranes": "odd_cards/split_agendas/jinteki_weyland_agenda.png",
    "project-oskoreia": "odd_cards/split_agendas/hb_nbn_agenda.png",
    "oddly-specific-horoscope": "odd_cards/split_agendas/jinteki_nbn_agenda.png",
    "flood-the-zone": "odd_cards/split_agendas/nbn_weyland_agenda.png",
}
LONG_BREAK = 1.7
SUBROUTINE_CHAR = chr(129)
REBOOT_INDICATOR = "\u0180" + chr(0x80)

# Budget solution for handling bold/superscript/symbols: putting the bold chars at offset X from the nonbold chars



class FontOffsets(NamedTuple):
    bold: int
    superscript: int
    bold_superscript: int
    champion: int


FLAVOR_OFFSETS = FontOffsets(
    bold=1185, superscript=389, bold_superscript=1574, champion=1718
)
TEXT_OFFSETS = FontOffsets(bold=531, superscript=0, bold_superscript=385, champion=0)
NO_OFFSETS = FontOffsets(bold=0, superscript=0, bold_superscript=0, champion=0)


class Box(NamedTuple):
    xmin: int
    ymin: int
    xmax: int
    ymax: int


class TemplateItem(str, Enum):
    """Some graphical element on a card."""

    TITLE = "title"
    SUBTITLE = "subtitle"
    TEXT = "text"
    FLAVOR = "flavor"
    SUBTYPE = "subtype"
    COST = "cost"
    ADVANCEMENT_REQUIREMENT = "advancement-requirement"
    AGENDA_POINTS = "agenda-points"
    MEMORY_COST = "memory-cost"
    TRASH_COST = "trash-cost"
    STRENGTH = "strength"
    BASE_LINK = "base-link"
    MINIMUM_DECK_SIZE = "minimum-deck-size"
    INFLUENCE_LIMIT = "influence-limit"
    TYPE = "type"
    ILLUSTRATOR = "illustrator"
    BACKSIDE_TITLE = "backside-title"
    SET_SYM_NUM = "set-sym-num"

CYCLE_SYMS = {                  # Maps each cycle code (01 = core, 10 = data & destiny, 50 = reflections) to the proper token in the illustrator font
    "01": "\u0181",
    "02": "\u0182",
    "03": "\u0183",
    "04": "\u0184",
    "05": "\u0185",
    "06": "\u0186",
    "07": "\u0187",
    "08": "\u0188",
    "09": "\u0189",
    "11": "\u018a",             # TODO: Decided to give reboots Reboot icon, so fix Psychokinesis not having this
    "50": "\u018a",
    "51": "\u018b",
    "52": "\u018c",
    "53": "\u018d",
    "54": "\u018e",
    "55": "\u018f",
    "70": "\u018f",
}


RESOURCE_DIR = pathlib.Path(__file__).parent / "assets"

try:
    CHANGED_CARD_CODES = set(json.loads(Path("changed_card_codes.json").read_text()))
except FileNotFoundError:
    CHANGED_CARD_CODES = []

def lookup_font_props(template_dict, card_faction, item):
    font_path = str(RESOURCE_DIR / template_dict[item]["font"])
    font_size = factionwise_template_lookup(
        template_dict, card_faction, item, "fontsize"
    )
    # TODO: add support for default to factionwise_template_lookup so this can be faciton-based
    # or maybe make the template dict a separate class...
    font_color = tuple(template_dict[item].get("fontcolor", (0, 0, 0)))

    return font_path, font_size, font_color


def get_text_dimensions(text_string, font):
    text_string = text_string.replace(chr(156), SUBROUTINE_CHAR)
    text_string = re.sub(r"<ral(\d{2})>", "", text_string)
    text_string = re.sub("<br>", "", text_string)

    bbox = font.getbbox(text_string)
    ascent, descent = font.getmetrics()

    width = bbox[2] - bbox[0]
    height = ascent + descent

    return width, height

def new_get_text_dimensions(text_string, font):
    # TODO: I want to port the generator to this to avoid clipping on ice strength, but this would break some other stuff, so for now I am not using it everywhere.
    text_string = text_string.replace(chr(156), SUBROUTINE_CHAR)
    text_string = re.sub(r"<ral(\d{2})>", "", text_string)
    text_string = re.sub("<br>", "", text_string)

    # Width: still measure glyphs
    bbox = font.getbbox(text_string)
    width = bbox[2] - bbox[0]

    # Height: baseline-safe, old Pillow behavior
    ascent, descent = font.getmetrics()
    height = ascent + descent

    return width, height

def get_text_dimensions(text_string, font):
    # very much like draw.textsize, but see  https://stackoverflow.com/a/46220683/9263761
    # ascent, descent = font.getmetrics() # if needed
    text_string = text_string.replace(chr(156), SUBROUTINE_CHAR)
    text_string = re.sub(r"<ral(\d{2})>", "", text_string)
    text_string = re.sub("<br>", "", text_string)

    if (bbox := font.getmask(text_string).getbbox()) is not None:
        # bbox = hori_offset, vert_offset, text_rect_width, text_rect_heihgt

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]  # + descent

        return (text_width, text_height)
    else:
        # Pillow ≥10: getsize() removed → use getbbox()
        bbox = font.getbbox(text_string)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        return (text_width, text_height)


def determine_line_breaks(
        text: str, font, img_draw, text_width: int, is_ice_text: bool
) -> tuple[list[str], int]:
    """Given some text and a max width, determine how large it will be, and where to break.
    Return the text as broken lines, and the total line height (including line spacing).
    Some line breaks are long and counted as LONG_BREAK length, and are indicated by lines ending in \n."""

    words = re.split(r"(\s+)", text)

    lines = []
    # Note: this is contingent on get_text_dimensions helping out, for baffling reasons
    SUBROUTINE_WIDTH_INDENT = chr(156) + " "
    have_seen_subroutine_symbol = False
    while words:
        line = ""  # words.pop(0)
        if is_ice_text and have_seen_subroutine_symbol and not lines[-1].endswith('\n'):
            line = SUBROUTINE_WIDTH_INDENT + line
        while words and (
            (not line) or get_text_dimensions(line + words[0], font)[0] < text_width
        ):
            w = words.pop(0)
            if w.startswith(SUBROUTINE_CHAR):
                have_seen_subroutine_symbol = True
            if w == "<br>":
                # \r is a space character, so will likely have surrounding spaces
                break
            if re.match("(\s)*\n+(\s)*", w):
                line += "\n"  # now lines end in '\n' if they should break long instead
                break
            line += w

        while words and words[0] == "\n":
            # the first word in each line is never checked for being a newline - two newlines do nothing (yet)
            words.pop(0)
            line += "\n"
        lines.append(line)

    total_line_height = len(lines) * get_text_dimensions("X", font=font)[1]

    return lines, total_line_height


def special_text_flavortext_handling(
    template_dict, card_dict, fontsize_fudge_factor: float = 1.0
) -> tuple[Image, int]:
    """Size text/flavortext is interdependent, so must be done concurrently. Pretty messy.
    Includes a vertical buffer on the top of the image, whose size is returned."""

    long_break_factor = card_dict.get("long-break-factor", LONG_BREAK)
    card_faction = card_dict["faction"]
    text_font_path, text_font_size, text_font_color = lookup_font_props(
        template_dict, card_faction, "text"
    )
    flavor_font_path, flavor_font_size, flavor_font_color = lookup_font_props(
        template_dict, card_faction, "flavor"
    )

    textwidth, textheight = [
        factionwise_template_lookup(template_dict, card_faction, "text", s)
        for s in ["width", "height"]
    ]

    card_text = make_item_text(card_dict, "text")
    flavor_text = make_item_text(card_dict, "flavor")
    if card_text is None:
        card_text = ""
    else:
        card_text = parse_text(card_text, font_offsets=TEXT_OFFSETS)
    if flavor_text is None:
        flavor_text = ""
    else:
        flavor_text = parse_text(flavor_text, font_offsets=FLAVOR_OFFSETS)

    M = max(textwidth, textheight)
    top_pad = 50  # TODO: hacky solution: add an extra H pixels on top to aovid clipping
    maximum_indent = 0
    if "eventual_indent" in template_dict["text"]:
        indent_thresholds: list[tuple[int, int]] = []
        for indent_dict in template_dict["text"]["eventual_indent"]:
            indent_thresholds.append((indent_dict["at_height"], indent_dict["indent"]))
            maximum_indent += indent_dict["indent"]
    else:
        indent_thresholds = [(0, 0)]
    retimg = Image.new(
        "RGBA", (M + top_pad + maximum_indent, M + top_pad), color=(0, 0, 0, 0)
    )
    draw = ImageDraw.Draw(retimg)
    extra_inter_spacing = 20

    # TODO: expose this from gui
    min_text_font_size = 16
    min_flavor_font_size = 11
    text_font_size = max(
        round(fontsize_fudge_factor * text_font_size), min_text_font_size
    )
    flavor_font_size = max(
        round(fontsize_fudge_factor * flavor_font_size), min_flavor_font_size
    )

    if card_dict.get("twiy-style-flavortext"):
        flavor_font_size = round(0.77 * flavor_font_size)
        extra_inter_spacing *= 6

    for text_font_size in range(text_font_size, min_text_font_size - 1, -1):
        # determine text size if this is what we do
        card_text_font = ImageFont.truetype(text_font_path, size=text_font_size)
        card_text_lines, total_card_text_height = determine_line_breaks(
            card_text, card_text_font, draw, textwidth, card_dict["type"] == "ice"
        )

        for flavor_font_size in range(flavor_font_size, min_flavor_font_size - 1, -1):
            # determine maximum possible flavor text
            if not flavor_text:
                free_vert_space = textheight - total_card_text_height
                break
            flavor_font = ImageFont.truetype(flavor_font_path, size=flavor_font_size)
            flavor_text_lines, total_flavor_text_height = determine_line_breaks(
                flavor_text, flavor_font, draw, textwidth, False
            )

            # insist on some inter-text spacing
            free_vert_space = textheight - (
                total_flavor_text_height + total_card_text_height + extra_inter_spacing
            )
            if free_vert_space > 0:
                # this works, so it must be the largest possible
                break
        else:
            # no flavor text is small enough
            continue

        # we have found something which works here - could try more, but seems expensive
        break

    # we have determined font sizes, now determine line break size
    free_vert_space = textheight - (
        (total_flavor_text_height + total_card_text_height)
        if flavor_text
        else total_card_text_height
    )

    # linebreak is ~50% of the font height, i.e. a little smaller for flavor text
    flavor_lb_pct = 0.5
    num_linebreaks = sum(
        [long_break_factor if line.endswith("\n") else 1 for line in card_text_lines]
    )
    if flavor_text:
        num_linebreaks += LONG_BREAK + flavor_lb_pct * sum(
            [
                long_break_factor if line.endswith("\n") else 1
                for line in flavor_text_lines
            ]
        )

    max_text_linespacing = free_vert_space / num_linebreaks
    max_flavor_linespacing = flavor_lb_pct * max_text_linespacing

    # TODO: here, make a temporary out-image, and return this for pasting instead

    x, y = 0, top_pad

    # finally, print everything on the image. x, y is location next line to print

    stuff_to_print = [
        (
            card_text_lines,
            ImageFont.truetype(text_font_path, text_font_size),
            text_font_color,
            max_text_linespacing,
        )
    ] + (
        [
            (
                flavor_text_lines,
                ImageFont.truetype(flavor_font_path, flavor_font_size),
                flavor_font_color,
                max_flavor_linespacing,
            )
        ]
        if flavor_text
        else []
    )

    is_printing_flavor = False
    for text_lines, font, font_color, max_linespacing in stuff_to_print:
        _, lineheight_est = get_text_dimensions("X", font=font)

        if flavor_text and max_linespacing == max_flavor_linespacing:
            linespacing = min(lineheight_est * 0.43, max_linespacing)
        else:
            linespacing = min(lineheight_est * 0.85, max_linespacing)

        long_linespacing = long_break_factor * linespacing

        def extract_number_from_prefix(s):
            import re

            # Regular expression to match the pattern <ralXX>
            pattern = r"^<ral(\d{2})>\s"

            # Using regex to find a match
            match = re.match(pattern, s)

            # If a match is found, extract and return the number, otherwise return None
            if match:
                return match.group(1)
            else:
                return None
        for line_idx, line in enumerate(text_lines, start=1):
            if (match := re.match("^\s*<ral(\d{2})>\s*", line)):
                line = line[len(match.group(0)):].strip()
                is_quote_line = True
                quote_dedent = int(match.group(1))
            else:
                is_quote_line = False
            _, lineheight = get_text_dimensions(line.strip(), font)
            is_long_break = line.endswith("\n")

            line = line.strip()
            # if is_printing_flavor and (not line.startswith('-') or line.startswith('<')):
            #     y += lineheight*0.25
            #     pass

            line_bottom = y + lineheight
            total_indent = 0
            for i, (height_treshold, indent_amount) in enumerate(indent_thresholds):
                if (line_bottom - top_pad) >= height_treshold:
                    total_indent += indent_amount

            if (card_dict.get("twiy-style-flavortext") and is_printing_flavor) or is_quote_line:
                line_width, _ = get_text_dimensions(line, font)
                space_width, _ = get_text_dimensions(' ', font)
                align_indent = textwidth - line_width - quote_dedent * space_width

            else:
                align_indent = 0

            draw.text(
                (x + total_indent + align_indent, y),
                line,
                font=font,
                fill=font_color,
                anchor="la",
            )
            y += lineheight_est

            if line_idx != len(text_lines):
                y += long_linespacing if is_long_break else linespacing

        y += extra_inter_spacing + LONG_BREAK * linespacing
        is_printing_flavor = True

    return retimg, top_pad


def make_item_text(card_dict, item) -> Optional[str]:
    """Determine how to/whether to write an attribute on the card."""
    card_type = card_dict["type"]
    if item == "subtype":
        subtype_replacements = {
            "ap": "AP",
            "next": "NEXT",
            "g-mod": "G-mod",
            "ai": "AI",
            "caissa": "Caïssa",
        }

        # manually added half space
        sep = chr(0x80) + "-" + chr(0x80)
        # sep = " - "

        text = sep.join(
            [
                subtype_replacements.get(st.lower(), st.replace("-", " ").title())
                for st in card_dict.get("subtype", [])
            ]
        )
    elif item == "type":
        if card_type == "identity":
            return None
        text = card_type.upper()
        if card_dict.get("subtype", []):
            text += ":"

    elif card_type == "identity" and item in {"title", "subtitle"}:
        text = card_dict["title"].split(": ")[0 if item == "title" else 1]
    elif item == "flavor":
        text = card_dict.get("flavor")
        if text is None:
            return None
    else:
        text = card_dict.get(item)
        if item == "title" and card_dict.get("uniqueness"):
            text = chr(128) + " " + text
        if item == "strength" and text == 11:  # this looks weird...
            text = "1" + chr(0x200B) + "1"

    if text is None:
        if (
            item in {"cost", "strength"}
            and card_type not in {"agenda", "identity"}
            and item in card_dict
        ):
            text = "X"
        else:
            return None
    return text


def factionwise_template_lookup(template_dict, faction, fieldname, propname):
    if faction not in {
        "anarch",
        "criminal",
        "haas-bioroid",
        "jinteki",
        "nbn",
        "neutral-corp",
        "neutral-runner",
        "shaper",
        "weyland-consortium",
    }:
        # must be apex, adam or sunny
        faction = "neutral-runner"
    prop = template_dict[fieldname][propname]

    if type(prop) is dict:
        if faction in prop:
            assert (
                faction in prop
            ), f"Could not find faction {faction} in {fieldname}:{propname} dict {str(prop)}"
            prop = prop[faction]
        else:
            # missing some support here...
            assert propname == "loc"
            assert "below-of" in prop, f"Didn't understand position directive {prop}"
            below_field = prop["below-of"]
            assert below_field == "text"

    return prop


def parse_text(text: str, font_offsets: FontOffsets) -> str:
    """Given card text from NRDB, strip formatting tags and replace
    icon symbols by the appropriate characters in the font. Use
    font_offsets to transform bold/superscript stuff (NO_OFFSETS for no change)."""
    # TODO: Must update the flavor font to include bold glyphs as well for this to be nice.

    # TODO: Things will break if <strong> stuff surrounds a symbol
    HALFSPACE = "\u0230"  # TODO: this will break if creds are used outside card text
    SYMBOL_TABLE = {
        "": "",
        "<em>": "",
        "</em>": "",
        "<li>": "\n " + chr(183) + " ",
        # TODO: Check which of these actually need the space still - better to fix it in font editor
        "[credit]": HALFSPACE + chr(127),
        "[link]": chr(128),
        "[subroutine]": SUBROUTINE_CHAR,
        "[recurring-credit]": chr(130),
        "[trash]": chr(131),
        "[click]": chr(132),
        "1[mu]": chr(134),
        "2[mu]": chr(135),
        "3[mu]": chr(136),
        "[mu]": chr(137),
        "[shaper]": chr(140) + " ",
        "[criminal]": chr(141) + " ",
        "[anarch]": chr(142) + " ",
        "[haas-bioroid]": chr(143) + " ",
        "[jinteki]": chr(144) + " ",
        "[nbn]": chr(145) + " ",
        "[weyland-consortium]": chr(146) + " ",
    }
    # The o in "don't twist me, dong ma?" is incorrect, and the font doesn't have this symbol
    text = text.replace("\u01d2", "ŏ")

    text = re.sub("<errata>(.*?)</errata>", "", text)
    for tag in ["strong", "champion"]:
        off = font_offsets.champion if tag == "champion" else font_offsets.bold
        text = re.sub(
            f"<{tag}>(.*?)</{tag}>",
            lambda m: "".join(
                [chr(ord(c) + (off if c != " " else 0)) for c in m.group(1)]
            ),
            text,
        )

    # Trace text is of the form <trace>Trace N</trace>, where N is a digit or X
    # We want to make the N into a superscript. The below handles 0-9 correctly, not X.
    text = re.sub(
        r"<trace>(Trace|trace) (\S*?)</trace>",
        lambda m: "".join(
            [chr(ord(c) + font_offsets.bold) for c in m.group(1)]
            + [
                chr(
                    (ord(c) if c != "X" else (1 + ord("9")))
                    + font_offsets.bold_superscript
                )
                for c in m.group(2)
            ]
        )
        + " –",
        text,
    )

    for symbol, font_char in SYMBOL_TABLE.items():
        text = text.replace(symbol, font_char)
    return text


def draw_text_on_image(
    template_dict,
    card_dict,
    item,
    text,
    draw,
    outimg,
    drawn_boxes: dict[TemplateItem, Box],
) -> Box:
    card_faction = card_dict["faction"]
    pos = factionwise_template_lookup(template_dict, card_faction, item, "loc")
    pos = tuple(pos)

    if card_dict.get("id") in SPLIT_AGENDA_RELPATHS and item == TemplateItem.SET_SYM_NUM:
        # Split agendas have a logo in the lower right, so need some nudging...
        pos = (pos[0]-130, pos[1])

    font_path = str(RESOURCE_DIR / template_dict[item]["font"])
    font_size = factionwise_template_lookup(
        template_dict, card_faction, item, "fontsize"
    )
    # TODO: add support for default to factionwise_template_lookup so this can be faction-based
    # or maybe make the template dict a separate class...
    font_color = tuple(template_dict[item].get("fontcolor", (0, 0, 0)))

    font_path, font_size, font_color = lookup_font_props(
        template_dict, card_faction, item
    )
    if card_dict['title'] == 'Double Down' and item == 'subtype': # Currently, this is literally the only card which cares, soooo
        font_size -= 2
        pos = (pos[0], pos[1]+1)

    font = ImageFont.truetype(font_path, size=font_size)

    if item == TemplateItem.SET_SYM_NUM and text.startswith(REBOOT_INDICATOR):
        if not template_dict[item].get("rotation"): # in this case it is top-aligned anyway
            rb_icon_width, _ = get_text_dimensions(REBOOT_INDICATOR, font)
            pos = (pos[0] - rb_icon_width, pos[1])
            

    # TODO: This should be using get_text_dimensions, but then all the template offsets must be fixed
    text_width, text_height = get_text_dimensions(str(text), font)

    if template_dict[item].get("center"):
        if (rot := template_dict[item].get("rotation")) is not None:
            assert (
                rot == 90
            ), "Currently do not support centering non-90 degree rotations"
        else:
            # TODO: should also center height here, but need to fix other templates first
            pos = (pos[0] - text_width / 2, pos[1])


    if template_dict[item].get("rotation") is None:
        if template_dict[item].get("backdrop"):
            bd_color = tuple(template_dict[item]["backdrop"]["color"])
            width = template_dict[item]["backdrop"]["width"]
            ox, oy = template_dict[item]["backdrop"]["offset"]
            for dx, dy in [
                (-width, -width),
                (width, -width),
                (-width, width),
                (width, width),
            ]:
                draw.text(
                    (pos[0] + dx + ox, pos[1] + dy + oy),
                    str(text),
                    font=font,
                    fill=bd_color,
                )

        draw.text(pos, str(text), font=font, fill=font_color)
        return Box(
            xmin=pos[0],
            ymin=pos[1],
            xmax=pos[0] + text_width,
            ymax=pos[1] + text_height,
        )
    else:
        # need to draw text at an angle
        # hang on to the bottom of the text to know where to start writing the time
        assert not template_dict[item].get(
            "backdrop"
        ), "Backdrop and rotation not supported"

        if item == "type" and card_dict["type"] == "ice":
            # Add the position from the template as an offset, because ICE:
            # gets weirdly high text height and for some spacing
            subtype_box = drawn_boxes[TemplateItem.SUBTYPE]
            pos = [pos[0] + subtype_box.xmin, pos[1] + subtype_box.ymax]

        # TODO: See refactor comment above this function.
        text_width, text_height = new_get_text_dimensions(str(text), font)
        M = max(text_width, text_height)
        tmpimg = Image.new("RGBA", (M, M), color=(0, 0, 0, 0))
        ImageDraw.Draw(tmpimg).text((0, 0), str(text), font=font, fill=font_color)
        tmpimg = tmpimg.rotate(template_dict[item].get("rotation"))

        if template_dict[item].get("center"):
            # try to ensure the text center is placed at the pos.
            assert (
                template_dict[item].get("rotation") == 90
            ), "Currently do not support centering non-90 degree rotations"
            # want to change coords so that when pasting upper left corner at _pos, this ends up at pos
            pos = (pos[0] - text_height / 2, pos[1] - (M - text_width / 2))

        _pos = tuple(map(round, pos))
        if template_dict[item].get("align_by_bottom_left_corner"):
            _pos = (_pos[0], _pos[1] - tmpimg.height)
        outimg.paste(tmpimg, _pos, mask=tmpimg)
        return Box(
            xmin=_pos[0],
            ymin=_pos[1],
            xmax=_pos[0] + text_height,
            ymax=_pos[1] + text_width,
        )

def maybe_post_midlunar_resource_adjustments(template_dict: dict):
    for k, v in list(template_dict["late_lunar_changes"].items()):
        template_dict[k] = v
    return template_dict

def make_card_proxy(card_dict, background_img_path, fudge_factor=1.0, make_alt=True, card_code="UNKNOWN_CARD_CODE"):
    # WIP number printing
    try:
        cycle_idx = int(card_code[2:])
        cycle_idx_str = str(cycle_idx)
        if len(cycle_idx_str) == 1: # not ideal, but numbers are inconsistently wide, so need this to not have it look a little odd
            space_prepend = "  " + chr(0x80)
        elif len(cycle_idx_str) == 2:
            space_prepend = " "
        else:
            space_prepend = ""
        cycle_idx_str = space_prepend + cycle_idx_str # core, genesis, spin, lunar, sansan had 100+ cards
        cycle_sym = CYCLE_SYMS[card_code[:2]]
        if card_code in CHANGED_CARD_CODES:
            cycle_sym = REBOOT_INDICATOR + cycle_sym
        card_dict["set-sym-num"] = f"{cycle_sym} {cycle_idx_str}"

    except ValueError:
        # Couldn't guess the card code
        card_dict["set-sym-num"] = ""
    # load card data

    card_type = card_dict["type"]

    # fetch appropriate template
    # TODO: hardcoding will break if script is symlinked, consider adding script to package instead
    # TODO: Also update the atoms
    if make_alt:
        template_path = RESOURCE_DIR / f"{card_type}_alt.yaml"
    else:
        template_path = RESOURCE_DIR / f"{card_type}.yaml"

    with open(template_path) as f:
        template_dict = yaml.safe_load(f)

    if card_type == "resource":
        try:
            cycle_num = int(card_code[:2])
            cycle_idx = int(card_code[2:])
            if (6 < cycle_num < 24) or (cycle_num == 6 and cycle_idx > 60):

                if (cycle_num, cycle_idx) != (23, 13): # crowdfunding
                    template_dict = maybe_post_midlunar_resource_adjustments(template_dict)
        except ValueError:      # Unknown card code, so no adjustment needed
            pass
    template_img_relpath = template_dict["template_image"][card_dict["faction"]]
    template_img_relpath = SPLIT_AGENDA_RELPATHS.get(card_dict.get("id"), template_img_relpath)

    if card_dict.get('is-flip-side'):
        template_img_relpath = template_img_relpath.replace('.png', '_flip.png')
        template_dict['title']['fontcolor'] = [255, 255, 255] # white text on black bg instead of opposite
    elif card_dict.get('backside-title'):
        template_img_relpath = template_img_relpath.replace('.png', '_flipfront.png')

    template_img_path = RESOURCE_DIR / template_img_relpath

    # load the template image and background
    template = Image.open(template_img_path).convert("RGBA")
    outimg = Image.new(mode="RGBA", size=(template.width, template.height))

    if background_img_path:
        bg = Image.open(background_img_path).convert("RGBA")
        bg = bg.resize((template.width, template.height))
        bg_offset = template_dict.get("img_offset", [0, 0])

        outimg.paste(bg, bg_offset)

    outimg.paste(template, mask=template)

    # TODO: could make all the template stuff relative to avoid hardcoding size
    outimg = outimg.resize((1720, 2400))

    draw = ImageDraw.Draw(outimg)

    drawn_elements: dict[str, Box] = {}

    # add inf dots
    if card_dict.get("influence-cost"):
        inf_pip_path = RESOURCE_DIR / template_dict["atoms"]["influence-pip"]
        infimg = Image.open(inf_pip_path).convert("RGBA")
        p0, p1 = [
            factionwise_template_lookup(
                template_dict, card_dict["faction"], f"influence-{i}", "loc"
            )
            for i in (1, 2)
        ]
        for i in range(card_dict["influence-cost"]):
            p = tuple(p0[j] + i * (p1[j] - p0[j]) for j in range(2))
            # now center
            p = (int(p[0] - infimg.width / 2), int(p[1] - infimg.height / 2))
            outimg.paste(infimg, p, mask=infimg)

    # add trashcan icon to trashable operations/ice
    if card_type in {"operation", "ice"} and card_dict.get("trash-cost") is not None:
        trashcan_path = RESOURCE_DIR / template_dict["atoms"]["trashcan"]
        trashcan = Image.open(trashcan_path).convert("RGBA")
        outimg.paste(trashcan, template_dict["trashcan"]["loc"], mask=trashcan)

    # now write everything else on there - the point of v_offset is because the top of the text can be clipped otherwise
    textbox_img, v_offset = special_text_flavortext_handling(
        template_dict, card_dict, fudge_factor
    )
    x, y = tuple(
        factionwise_template_lookup(template_dict, card_dict["faction"], "text", "loc")
    )
    if (textbox_rotation := template_dict["text"].get("rotation")) is not None:
        assert textbox_rotation == 90, "Only 90 degree rotation of text box supported"
        assert (
            "eventual_indent" not in card_dict["text"]
        ), "Cannot indent parts of text while rotating!"
        textbox_img = textbox_img.rotate(textbox_rotation)
        # in this case, we align by bottom left corner because convention
        outimg.paste(
            textbox_img, (x - v_offset, y - textbox_img.height), mask=textbox_img
        )
    else:
        outimg.paste(textbox_img, (x, y - v_offset), mask=textbox_img)

    for item_enum in TemplateItem:
        item = item_enum.value
        if item in {"text", "flavor"}:
            continue
        text = make_item_text(card_dict, item)
        
        if text is None or text == "":
            continue

        text = str(text)
        drawn_elements[item_enum] = draw_text_on_image(
            template_dict, card_dict, item, text, draw, outimg, drawn_elements
        )

    return outimg

    # orig_path = Path(output_path).with_stem(Path(output_path).stem + "_original")
    # bg.convert("RGB").save(orig_path)


def pyfy(obj):
    """Transform clojure-y objects into the Python analogues."""
    if type(obj) is edn_format.edn_lex.Keyword:
        return str(obj)[1:]
    elif type(obj) is edn_format.immutable_list.ImmutableList:
        return [pyfy(subobj) for subobj in obj]
    else:
        return obj


def parse_input_and_doit():
    make_alt = False  # TODO: add option
    try:
        edn_path = sys.argv[1]
        with open(edn_path) as f:
            d = edn_format.edn_parse.parse(f.read())
            card_dict = {pyfy(k): pyfy(v) for k, v in d.items()}

        output_path = sys.argv[2]
        code_dict = yaml.safe_load(
            Path("/home/karlerik/hobby/netrunner-data/card_image_generator/cardgen_data/code_dict.json").read_text()
        )
        card_name = Path(edn_path).stem
        _card_name = card_dict.get("id")  # TODO: hack...
        _card_code = code_dict.get(_card_name, "UNKNOWN_CARD_CODE")
        card_code = code_dict.get(card_name, "UNKNOWN_CARD_CODE")

        if card_code == "UNKNOWN_CARD_CODE" and card_name.endswith("-front") or card_name.endswith("-back"):
            card_code = code_dict.get("-".join(card_name.split("-")[:-1]), "UNKNOWN_CARD_CODE")
        

        # horrible hack...
        if len(sys.argv) > 4 and sys.argv[4] == "--font-fudge":
            fudge_factor = float(sys.argv[5])
            sys.argv = sys.argv[:4] + sys.argv[6:]
        elif "font-fudge-factor" in card_dict and not make_alt:
            fudge_factor = card_dict.pop("font-fudge-factor")
        else:
            fudge_factor = 1.0

        background_img_path = f"/home/karlerik/hobby/aligned_images/{card_code}.jpg"
        if card_name in ['sync-front', 'sync-back', 'biotech-front', 'biotech-brewery', 'biotech-greenhouse', 'biotech-tank']:
            background_img_path = f"/home/karlerik/hobby/aligned_images/special_images/{card_name.replace('-', '_')}.jpg"
        if not pathlib.Path(background_img_path).exists():
            background_img_path = sys.argv[3]
            assert pathlib.Path(
                background_img_path
            ).exists(), "background image doesn't exist??"

    except IndexError as e:
        print(
            "Usage: python proxygen.py path_to_card_data_edn output_image_path <optional: background_image_path>"
        )
        sys.exit(1)

    with open(
        "/home/karlerik/hobby/reteki_data/card_image_generator/cardgen_data/card_illustrator_dict.json"
    ) as f:
        illustrator_dict = json.load(f)
    if (
        "illustrator" not in card_dict
        and _card_code in illustrator_dict
        and "illustrator" in illustrator_dict[_card_code]
    ):
        card_dict["illustrator"] = illustrator_dict[_card_code]["illustrator"]
    if "illustrator" in card_dict:
        card_dict["illustrator"] = f'Illus.: {card_dict["illustrator"]}'


    # DEV STUFF
    card_dict["set-sym-num"] = " 25"
        
    make_alt = False  # TODO: add option
    if "flavor" not in card_dict and (
        flavor := illustrator_dict.get(card_code, {}).get("flavor")
    ):
        # TODO: add support for this alignment back in? or just ignore? tempted to ignore
        # flavor = flavor.replace('" -', '"\n\0-')
        # flavor = flavor.replace('"\n-', '"\n\0-')
        # print(repr(flavor))

        card_dict["flavor"] = flavor

    if "strength" not in card_dict and card_dict["type"] == "program":
        card_dict["strength"] = "–"

    if minifaction := PREMADE_IDS.get(card_code):
        proxy_img_path = RESOURCE_DIR / "odd_cards" / f"{minifaction}.jpg"
        Path(output_path).write_bytes(proxy_img_path.read_bytes())
        q = 95
        Image.open(proxy_img_path).save(
            output_path,
            **(
                {"quality": q}
                if output_path.lower().split(".")[-1] in {"jpg", "jpeg"}
                else {}
            ),
        )

    else:
        outimg = make_card_proxy(
            card_dict, background_img_path, fudge_factor=fudge_factor, make_alt=make_alt, card_code=card_code
        )
        # convert to RGB to apply transparency mask from template, PIL is weird about it otherwise
        q = 95
        output_suffix = output_path.lower().split(".")[-1]
        outimg.convert("RGB").save(
            output_path, **({"quality": q} if output_suffix in {"jpg", "jpeg"} else {})
        )


if __name__ == "__main__":
    parse_input_and_doit()
