import json
import re
import sys
from tempfile import NamedTemporaryFile

from django.core.management.base import BaseCommand
from django.db import transaction

import requests
from tqdm import tqdm

from baserow.contrib.database.airtable.config import AirtableImportConfig
from baserow.contrib.database.airtable.constants import AIRTABLE_BASE_URL
from baserow.contrib.database.airtable.exceptions import AirtableBaseNotPublic
from baserow.contrib.database.airtable.handler import BASE_HEADERS, AirtableHandler
from baserow.contrib.database.airtable.utils import (
    parse_json_and_remove_invalid_surrogate_characters,
)
from baserow.core.models import Workspace
from baserow.core.utils import Progress, remove_invalid_surrogate_characters


class Command(BaseCommand):
    help = (
        "This command fetches all Airtable templates, and attemps to import them into "
        "the given workspace. It's created for testing purposes of the Airtable import."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "workspace_id",
            type=int,
            help="The workspace ID where a copy of the imported Airtable base must be "
            "added to.",
        )
        parser.add_argument(
            "--start",
            type=int,
            help="From which index should the import start.",
            default=0,
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="The maximum number of templates to install.",
            default=-1,
        )

    def handle(self, *args, **options):
        workspace_id = options["workspace_id"]
        start_index = options["start"]
        limit = options["limit"]

        try:
            workspace = Workspace.objects.get(pk=workspace_id)
        except Workspace.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"The workspace with id {workspace_id} was not found.")
            )
            sys.exit(1)

        html_url = f"{AIRTABLE_BASE_URL}/templates"
        html_response = requests.get(html_url, headers=BASE_HEADERS)  # nosec

        if not html_response.ok:
            raise Exception("test")

        decoded_content = remove_invalid_surrogate_characters(html_response.content)
        raw_init_data = re.search(
            "window.initData = (.*?)<\\/script>", decoded_content
        ).group(1)
        init_data = json.loads(raw_init_data)
        client_code_version = init_data["codeVersion"]
        page_load_id = init_data["pageLoadId"]

        templates_url = (
            f"{AIRTABLE_BASE_URL}/v0.3/exploreApplications"
            f"?templateStatus=listed"
            f"&shouldDisplayFull=true"
            f"&descriptionSnippetMaxLength=300"
            f"&categoryType=templateDesktopV2"
        )

        response = requests.get(
            templates_url,
            headers={
                "x-airtable-inter-service-client": "webClient",
                "x-airtable-inter-service-client-code-version": client_code_version,
                "x-airtable-page-load-id": page_load_id,
                "X-Requested-With": "XMLHttpRequest",
                "x-time-zone": "Europe/Amsterdam",
                "x-user-locale": "en",
                **BASE_HEADERS,
            },
            timeout=3 * 60,
        )  # nosec

        json_decoded_content = parse_json_and_remove_invalid_surrogate_characters(
            response
        )

        applications_by_id = json_decoded_content["exploreApplicationsById"].values()
        i = 0
        for index, application in enumerate(applications_by_id):
            share_id = application["shareId"]
            title = application["title"]

            if limit != -1 and i >= limit:
                print("finished!")
                return

            if index < start_index - 1:
                print(
                    f"Skipping {title} {share_id} {index + 1}/{len(applications_by_id)}"
                )
                continue

            i += 1
            print(
                f"Going to import {title} {share_id} {index + 1}/{len(applications_by_id)}"
            )

            with tqdm(total=1000) as progress_bar:
                progress = Progress(1000)

                def progress_updated(percentage, state):
                    progress_bar.set_description(state)
                    progress_bar.update(progress.progress - progress_bar.n)

                progress.register_updated_event(progress_updated)

                with NamedTemporaryFile() as download_files_buffer:
                    config = AirtableImportConfig(skip_files=True)
                    with transaction.atomic():
                        try:
                            AirtableHandler.import_from_airtable_to_workspace(
                                workspace,
                                share_id,
                                progress_builder=progress.create_child_builder(
                                    represents_progress=progress.total
                                ),
                                download_files_buffer=download_files_buffer,
                                config=config,
                            )
                        except AirtableBaseNotPublic:
                            print("  Skipping because it's not public.")
