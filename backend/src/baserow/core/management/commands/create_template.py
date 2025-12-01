import json
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a template with the given file name."

    def add_arguments(self, parser):
        parser.add_argument(
            "template_file_name",
            type=str,
            help="The file name of the template to create.",
        )
        parser.add_argument(
            "--from-export",
            type=str,
            help="The file name of the export file to create the template from.",
        )

    def handle(self, *args, **options):
        template_file_name = options["template_file_name"]
        from_export_file_name = options["from_export"]
        template_json = {
            "baserow_template_version": 1,
            "name": template_file_name,
            "icon": "iconoir-user",
            "keywords": ["Template"],
            "categories": ["Test category 1"],
            "export": [],
        }

        templates_dir = Path(settings.APPLICATION_TEMPLATES_DIR)
        template_path = templates_dir / f"{template_file_name}.json"

        if from_export_file_name:
            current_path = Path.cwd()
            exported_json_file_path = current_path / f"{from_export_file_name}.json"
            exported_zip_file_path = current_path / f"{from_export_file_name}.zip"

            with open(exported_json_file_path, "r") as json_file:
                exported_json = json.loads(json_file.read())
                template_json["export"] = exported_json

            with open(template_path, "w") as template_json_file:
                json.dump(template_json, template_json_file, indent=4)

            new_zip_file_path = template_path.with_name(f"{template_file_name}.zip")
            shutil.copyfile(exported_zip_file_path, new_zip_file_path)
        else:
            with open(template_path, "w") as template_json_file:
                json.dump(template_json, template_json_file, indent=4)
        self.stdout.write(self.style.SUCCESS(f"Template created: {template_path}"))
