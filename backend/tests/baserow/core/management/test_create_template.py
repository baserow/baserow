import json
from pathlib import Path

from django.core.management import call_command
from django.test import override_settings


def test_create_template_starts_with_empty_description(tmpdir):
    with override_settings(APPLICATION_TEMPLATES_DIR=str(tmpdir)):
        call_command("create_template", "new-template")

    template_json = json.loads((Path(tmpdir) / "new-template.json").read_text())
    assert template_json["description"] == ""
