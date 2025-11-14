#!/usr/bin/env python3

import os
import shutil
from pathlib import Path
from typing import Optional

import typer

from domains import domain_types, DatabaseDomain
from changelog_entry import changelog_entry_types, BugChangelogEntry
from click import Choice
from handler import ChangelogHandler

app = typer.Typer()

# Parent directory
default_path = str(Path(os.path.dirname(__file__)).parent)


@app.command()
def add(working_dir: Optional[str] = typer.Option(default=default_path)):
    domain_type = typer.prompt(
        "Domain",
        type=Choice(list(domain_types.keys())),
        default=DatabaseDomain.type,
    )
    changelog_type = typer.prompt(
        "Type of changelog",
        type=Choice(list(changelog_entry_types.keys())),
        default=BugChangelogEntry.type,
    )
    issue_number = typer.prompt(
        "Issue number", type=str, default=ChangelogHandler.get_issue_number() or ""
    )

    message = typer.prompt("Message", default="")

    if issue_number.isdigit():
        issue_number = int(issue_number)

    if issue_number == "":
        issue_number = None

    ChangelogHandler(working_dir).add_entry(
        domain_type,
        changelog_type,
        message,
        issue_number=issue_number,
        issue_origin="github",  # All new changelogs originate from GitHub
    )


@app.command()
def release(
    name: str,
    working_dir: Optional[str] = typer.Option(default=default_path),
):
    changelog_handler = ChangelogHandler(working_dir)

    if not changelog_handler.is_release_name_unique(str(name)):
        raise Exception(f"A release with the name {name} already exists.")

    changelog_handler.move_entries_to_release_folder(name)
    changelog_handler.write_release_meta_data(name)
    changelog_handler.generate_changelog_markdown_file()


@app.command()
def purge(working_dir: Optional[str] = typer.Option(default=default_path)):
    changelog_handler = ChangelogHandler(working_dir)

    try:
        shutil.rmtree(changelog_handler.entries_file_path)
        os.remove(changelog_handler.release_meta_data_file_path)
        os.remove(changelog_handler.changelog_path)
    except FileNotFoundError:
        pass


@app.command()
def generate(working_dir: Optional[str] = typer.Option(default=default_path)):
    changelog_handler = ChangelogHandler(working_dir)
    changelog_handler.generate_changelog_markdown_file()


if __name__ == "__main__":
    app()
