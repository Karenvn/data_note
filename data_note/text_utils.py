#!/usr/bin/env python


def oxford_comma_list(items: list[str]) -> str:
    if len(items) == 0:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def format_location(location_string):
    if not location_string:
        return ""
    parts = [part.strip() for part in location_string.split("|")]
    return ", ".join(reversed(parts)).title()


def to_title_case(value):
    if isinstance(value, str):
        return value.title()
    return value


def replace_special_characters(text, target_format="word"):
    replacements = {
        "&": {"word": "&amp;", "xml": "\u0026"},
        "<": {"word": "&lt;", "xml": "\u003C"},
        ">": {"word": "&gt;", "xml": "\u003E"},
        '"': {"word": "&quot;", "xml": "\u0022"},
        "'": {"word": "&apos;", "xml": "\u0027"},
    }

    for char, formats in replacements.items():
        replacement = formats.get(target_format, char)
        text = text.replace(char, replacement)

    return text
