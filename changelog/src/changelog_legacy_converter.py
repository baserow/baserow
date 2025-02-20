from pathlib import Path
from typing import List

from domains import DatabaseDomain
from changelog_entry import (
    BreakingChangeChangelogEntry,
    BugChangelogEntry,
    FeatureChangelogEntry,
    RefactorChangelogEntry,
)
from handler import LINE_BREAK_CHARACTER, ChangelogHandler

DETECTABLE_CHARACTERS = {
    "HEADING": "#",
    "ENTRY": "*",
    "UNRELEASED_HEADING": "## Unreleased",
    "RELEASE_HEADING": "## Released",
    "CHANGELOG_TYPE": "###",
}

CHANGELOG_HEADING_TO_TYPE_MAP = {
    "Bug Fixes": BugChangelogEntry.type,
    "New Features": FeatureChangelogEntry.type,
    "Refactors": RefactorChangelogEntry.type,
    "Breaking": BreakingChangeChangelogEntry.type,
}


def is_bullet_point(line: str):
    return line.startswith(" ") and line.strip().startswith("*")


def extract_issue_number(entry: str):
    entry = entry.removeprefix("*")
    try:
        [message, remainder] = entry.split("[#")
        issue_number = int(remainder.split("]")[0])
    except ValueError:
        message = entry
        issue_number = None

    return message.strip(), issue_number


def create_release_folder(name: str):
    Path(f"src/entries/{name}").mkdir(parents=True, exist_ok=True)


def does_not_start_with_any(text: str, characters: List[str]):
    for character in characters:
        if text.startswith(character):
            return False
    return True


def is_line_empty(line):
    return line == "" or line == " " or line == "\n"


def next_line(lines: List[str], i: int):
    if i >= len(lines):
        return None
    return lines[i]


def sanitise_release_name(release_name: str):
    return release_name.replace(" ", "_").strip()


def main():
    changelog_file = open("../changelog.md", "r")

    lines = changelog_file.readlines()

    current_release = None
    current_changelog_type = None
    releases_added = []

    i = 0
    while i < len(lines):
        line = next_line(lines, i)

        if line.startswith(DETECTABLE_CHARACTERS["ENTRY"]):
            entry = line.strip()
            bullet_points = []

            local_counter = i + 1
            line_to_check = next_line(lines, local_counter)

            while (
                line_to_check is not None
                and not is_line_empty(line_to_check)
                and does_not_start_with_any(
                    line_to_check, list(DETECTABLE_CHARACTERS.values())
                )
            ):
                if is_bullet_point(line_to_check):
                    bullet_point = line_to_check.strip().removeprefix("*").strip()
                    bullet_points.append(bullet_point)
                else:
                    entry += f"{LINE_BREAK_CHARACTER}{line_to_check.strip()}"

                local_counter += 1
                line_to_check = next_line(lines, local_counter)

            message, issue_number = extract_issue_number(entry)

            # For the ones that didn't have headers we treat them all like
            # features
            if current_changelog_type is None:
                current_changelog_type = FeatureChangelogEntry.type

            ChangelogHandler().add_entry(
                DatabaseDomain.type,
                current_changelog_type,
                message,
                issue_number,
                release=current_release,
                bullet_points=bullet_points,
            )

            i = local_counter
            continue

        elif line.startswith(DETECTABLE_CHARACTERS["RELEASE_HEADING"]):
            current_release = line.removeprefix(
                DETECTABLE_CHARACTERS["RELEASE_HEADING"]
            ).strip()
            current_release = sanitise_release_name(current_release)

            create_release_folder(current_release)
            releases_added.append(current_release)
            current_changelog_type = None

        elif line.startswith(DETECTABLE_CHARACTERS["UNRELEASED_HEADING"]):
            current_release = sanitise_release_name("unreleased")
            create_release_folder(current_release)
            current_changelog_type = None

        elif line.startswith(DETECTABLE_CHARACTERS["CHANGELOG_TYPE"]):
            heading = line.removeprefix("###").strip()

            for key, value in CHANGELOG_HEADING_TO_TYPE_MAP.items():
                if key in heading:
                    current_changelog_type = value

        elif is_line_empty(line):
            pass
        elif line is None:
            return print("done")
        else:
            print("[Undetected line]", line)

        i += 1

    # We have to reverse because we need the latest release to be added first
    releases_added.reverse()
    for release_name in releases_added:
        ChangelogHandler().write_release_meta_data(release_name)


if __name__ == "__main__":
    main()
