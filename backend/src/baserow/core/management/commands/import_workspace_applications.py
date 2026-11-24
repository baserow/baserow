import json
import os
import sys

from django.core.management.base import BaseCommand
from django.db import transaction

from baserow.core.handler import CoreHandler
from baserow.core.management.commands.export_workspace_applications import (
    cli_import_export_config,
)
from baserow.core.models import Workspace
from baserow.core.signals import application_imported


class Command(BaseCommand):
    help = (
        "Imports an exported JSON file and optionally a ZIP file containing the files. "
        "The applications are added to the provided workspace id. Exports generated "
        "by the `export_workspace_applications` are compatible. If for example the "
        "workspace with ID 10 has been exported then you probably need to run this "
        "command with the following arguments: `NEW_WORKSPACE_ID workspace_10`."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "workspace_id",
            type=int,
            help="The id of the workspace where the newly created applications must be "
            "added to.",
        )
        parser.add_argument(
            "name",
            type=str,
            help="The name of the export. An export is by default named "
            "`workspace_{ID}`. At least a JSON file with the given name is "
            "expected in the working directory.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        workspace_id = options["workspace_id"]
        name = options["name"]

        try:
            workspace = Workspace.objects.get(pk=workspace_id)
        except Workspace.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"The workspace with id {workspace_id} was not found.")
            )
            sys.exit(1)

        current_path = os.path.abspath(os.getcwd())
        files_path = os.path.join(current_path, f"{name}.zip")
        import_path = os.path.join(current_path, f"{name}.json")
        handler = CoreHandler()
        # What the export holds beside its applications. Nobody imports, so the
        # applications wait for the identities it describes.
        workspace_objects = None
        objects_path = os.path.join(current_path, f"{name}.workspace_objects.json")
        if os.path.exists(objects_path):
            with open(objects_path, "r") as objects_buffer:
                workspace_objects = json.load(objects_buffer)

        with open(import_path, "r") as import_buffer:
            content = json.load(import_buffer)
            files_buffer = None

            try:
                files_buffer = open(files_path, "rb")
            except FileNotFoundError:
                self.stdout.write(
                    f"The `{name}.zip` was not found. This could result in error or "
                    f"missing files."
                )

            # By default, we won't import any registry data. This is because
            # `RoleAssignment` can't be imported if the subjects are teams.
            applications, _ = handler.import_applications_to_workspace(
                workspace,
                content,
                files_buffer,
                cli_import_export_config,
                workspace_objects=workspace_objects,
            )

            if files_buffer:
                files_buffer.close()

            for application in applications:
                application_imported.send(self, application=application, user=None)

        self.stdout.write(f"{len(applications)} application(s) has/have been imported.")
