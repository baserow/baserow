import sys
from tempfile import NamedTemporaryFile

from django.core.management.base import BaseCommand
from django.db import transaction

from tqdm import tqdm

from baserow.contrib.database.airtable.config import AirtableImportConfig
from baserow.contrib.database.airtable.exceptions import AirtableBaseNotPublic
from baserow.contrib.database.airtable.handler import AirtableHandler
from baserow.contrib.database.airtable.utils import extract_share_id_from_url
from baserow.core.models import Workspace
from baserow.core.utils import Progress


class Command(BaseCommand):
    help = (
        "This management command copies all the data from a publicly shared Airtable "
        "base and tries to import a copy into the provided workspace. A base can be "
        "shared publicly by clicking on the `Share` button in the top right corner and "
        "then create a `Shared base link`. The resulting URL must be provided as "
        "argument."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "workspace_id",
            type=int,
            help="The workspace ID where a copy of the imported Airtable base must be "
            "added to.",
        )
        parser.add_argument(
            "public_base_url",
            type=str,
            help="The URL of the publicly shared Airtable base "
            "(e.g. https://airtable.com/shrxxxxxxxxxxxxxx).",
        )
        parser.add_argument(
            "--skip-files",
            action="store_true",
            help="When provided, the files will not be downloaded and imported.",
        )
        parser.add_argument(
            "--airtable-session",
            type=str,
            default="",
            help="",
        )
        parser.add_argument("--airtable-signature", type=str, help="", default="")

    @transaction.atomic
    def handle(self, *args, **options):
        workspace_id = options["workspace_id"]
        public_base_url = options["public_base_url"]
        skip_files = options["skip_files"]
        airtable_session = options["airtable_session"]
        airtable_signature = options["airtable_signature"]

        if bool(airtable_session) != bool(airtable_signature):
            self.stderr.write(
                self.style.ERROR(
                    "Both --airtable-session and --airtable-signature must either be "
                    "provided together or omitted together."
                )
            )
            sys.exit(1)

        try:
            workspace = Workspace.objects.get(pk=workspace_id)
        except Workspace.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"The workspace with id {workspace_id} was not found.")
            )
            sys.exit(1)

        try:
            share_id = extract_share_id_from_url(public_base_url)
        except ValueError as e:
            self.stdout.write(self.style.ERROR(str(e)))
            sys.exit(1)

        with tqdm(total=1000) as progress_bar:
            progress = Progress(1000)

            def progress_updated(percentage, state):
                progress_bar.set_description(state)
                progress_bar.update(progress.progress - progress_bar.n)

            progress.register_updated_event(progress_updated)

            try:
                with NamedTemporaryFile() as download_files_buffer:
                    config = AirtableImportConfig(
                        skip_files=skip_files,
                        session=airtable_session,
                        session_signature=airtable_signature,
                    )
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
                self.stdout.write(
                    self.style.ERROR(
                        "The Airtable base is not shared publicly. A base can be "
                        "shared publicly by clicking on the `Share` button in the "
                        "top right corner and then create a `Shared base link`."
                    )
                )
                sys.exit(1)

        self.stdout.write(f"Your base has been imported.")
