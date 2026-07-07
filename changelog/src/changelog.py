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

DOMAIN_TYPES = list(domain_types.keys())
ENTRY_TYPES = list(changelog_entry_types.keys())


@app.command()
def add(
    working_dir: Optional[str] = typer.Option(default=default_path),
    domain: Optional[str] = typer.Option(None, "--domain", help=f"The module domain this changelog pertains to. One of: {', '.join(DOMAIN_TYPES)}."),
    entry_type: Optional[str] = typer.Option(
        None, "--type", help=f"The entry type this changelog is. One of: {', '.join(ENTRY_TYPES)}.",
    ),
    message: Optional[str] = typer.Option(
        None, "--message", help="The changelog message. Describe in non-technical language what the bug, feature or refactor accomplishes."
    ),
    issue: Optional[str] = typer.Option(None, "--issue", help="The GitHub issue ID. Defaults to finding it through the branch name prefix."),
):
    domain_type = domain or typer.prompt(
        "Domain",
        type=Choice(DOMAIN_TYPES),
        default=DatabaseDomain.type,
    )
    if domain_type not in DOMAIN_TYPES:
        raise typer.BadParameter(
            f"must be one of: {', '.join(DOMAIN_TYPES)}", param_hint="--domain"
        )

    changelog_type = entry_type or typer.prompt(
        "Type of changelog",
        type=Choice(ENTRY_TYPES),
        default=BugChangelogEntry.type,
    )
    if changelog_type not in ENTRY_TYPES:
        raise typer.BadParameter(
            f"must be one of: {', '.join(ENTRY_TYPES)}",
            param_hint="--type",
        )
    if issue is not None:
        issue_number = issue
    elif domain is not None and entry_type is not None and message is not None:
        issue_number = ChangelogHandler.get_issue_number() or ""
    else:
        issue_number = typer.prompt(
            "Issue number", type=str, default=ChangelogHandler.get_issue_number() or ""
        )
    final_message = message or typer.prompt("Message", default="")

    if issue_number and not str(issue_number).isdigit():
        raise typer.BadParameter("must be a numeric GitHub issue ID", param_hint="--issue")

    if str(issue_number).isdigit():
        issue_number = int(issue_number)

    if issue_number == "":
        issue_number = None

    path = ChangelogHandler(working_dir).add_entry(
        domain_type,
        changelog_type,
        final_message,
        issue_number=issue_number,
        issue_origin="github",  # All new changelogs originate from GitHub
    )
    typer.echo(path)


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
