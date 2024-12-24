import json
import os
import sys

from django.core.management.base import BaseCommand

from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.registries import ImportExportConfig

cli_import_export_config = ImportExportConfig(
    include_permission_data=False,
    reduce_disk_space_usage=False,
    exclude_sensitive_data=True,
)


class Command(BaseCommand):
    help = (
        "Exports all the application of a workspace to a JSON file that can later be "
        "imported via the `import_workspace_applications` management command. "
        "A ZIP file containing all the files is also exported, this will for example "
        "contain the files uploaded to a file field."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "workspace_id",
            type=int,
            help="The id of the workspace that " "must be exported.",
        )
        parser.add_argument(
            "--indent",
            action="store_true",
            help="Indicates if the JSON must be formatted and indented to improve "
            "readability.",
        )
        parser.add_argument(
            "--name",
            type=str,
            help="The JSON and ZIP files are going to be named `workspace_ID.json` and "
            "`workspace_ID.zip` by default, but can optionally be named differently by "
            "proving this argument.",
        )

    def handle(self, *args, **options):
        workspace_id = options["workspace_id"]
        indent = options["indent"]
        name = options["name"]

        try:
            workspace = Workspace.objects.get(pk=workspace_id)
        except Workspace.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"The workspace with id {workspace_id} was not found.")
            )
            sys.exit(1)

        file_name = name or f"workspace_{workspace.id}"
        current_path = os.path.abspath(os.getcwd())
        files_path = os.path.join(current_path, f"{file_name}.zip")
        export_path = os.path.join(current_path, f"{file_name}.json")

        # By default, we won't export any registry data. This is because
        # `RoleAssignment` can't be exported->imported across workspaces
        # if the subjects are teams, or if the user subject doesn't belong
        # to the imported workspace.
        with open(files_path, "wb") as files_buffer:
            exported_applications = CoreHandler().export_workspace_applications(
                workspace,
                files_buffer=files_buffer,
                import_export_config=cli_import_export_config,
            )

        with open(export_path, "w") as export_buffer:
            json.dump(
                exported_applications, export_buffer, indent=2 if indent else None
            )
