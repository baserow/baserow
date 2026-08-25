from unittest.mock import patch

from django.core.management import call_command

import pytest

from baserow_enterprise.assistant.evals.export import export_foreign_examples


class _FakeDataset:
    def __init__(self, examples):
        self.examples = examples


class _FakeDatasetsAPI:
    def __init__(self, dataset):
        self._dataset = dataset
        self.get_dataset_calls: list[dict] = []

    def get_dataset(self, **kwargs):
        self.get_dataset_calls.append(kwargs)
        return self._dataset


class _FakeClient:
    def __init__(self, dataset):
        self.datasets = _FakeDatasetsAPI(dataset)


def _code_owned_example(case_id: str) -> dict:
    return {
        "id": case_id,
        "node_id": case_id,
        "input": {"prompt": "already in code"},
        "output": {},
        "metadata": {"case_id": case_id},
    }


def _foreign_example(
    prompt: str, metadata: dict | None = None, output: dict | None = None
) -> dict:
    return {
        "id": "RGF0YXNldEV4YW1wbGU6NQ==",
        "node_id": "RGF0YXNldEV4YW1wbGU6NQ==",
        "input": {"prompt": prompt},
        "output": output or {},
        "metadata": metadata or {},
    }


class TestExportForeignExamplesDocs:
    def test_no_foreign_examples_reports_nothing_to_export(self):
        dataset = _FakeDataset([_code_owned_example("docs/case-1")])
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-docs")

        assert "No UI-added examples" in output
        assert "_register_docs_case" not in output

    def test_code_owned_examples_are_not_exported(self):
        dataset = _FakeDataset(
            [_code_owned_example("docs/case-1"), _foreign_example("a new question")]
        )
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-docs")

        assert output.count("_register_docs_case(") == 1

    def test_emits_register_docs_case_call_with_prompt(self):
        dataset = _FakeDataset(
            [_foreign_example("How do I share a view with a client?")]
        )
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-docs")

        assert "_register_docs_case(" in output
        assert "How do I share a view with a client?" in output

    def test_id_is_kebab_slug_of_first_six_words_with_todo(self):
        dataset = _FakeDataset(
            [_foreign_example("How do I share a view with a client please")]
        )
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-docs")

        assert "'how-do-i-share-a-view'" in output
        assert "docs/how-do-i-share-a-view" in output
        assert "TODO verify id" in output

    def test_expected_keywords_from_metadata_when_set(self):
        dataset = _FakeDataset(
            [_foreign_example("q", metadata={"expected_keywords": ["share", "public"]})]
        )
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-docs")

        assert "['share', 'public']" in output
        assert "TODO-keyword" not in output

    def test_expected_keywords_placeholder_when_absent(self):
        dataset = _FakeDataset([_foreign_example("q")])
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-docs")

        assert "TODO-keyword" in output

    def test_expected_source_patterns_from_metadata_when_set(self):
        dataset = _FakeDataset(
            [
                _foreign_example(
                    "q", metadata={"expected_source_patterns": ["link-to-table"]}
                )
            ]
        )
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-docs")

        assert "['link-to-table']" in output
        assert "TODO-source-pattern" not in output

    def test_expected_source_patterns_placeholder_when_absent(self):
        dataset = _FakeDataset([_foreign_example("q")])
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-docs")

        assert "TODO-source-pattern" in output

    def test_header_points_at_docs_py(self):
        dataset = _FakeDataset([_foreign_example("q")])
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-docs")

        assert "datasets/docs.py" in output
        assert "just b eval-sync" in output

    def test_reference_answer_included_when_output_carries_one(self):
        dataset = _FakeDataset(
            [_foreign_example("q", output={"reference_answer": "Use date_diff()."})]
        )
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-docs")

        assert "reference_answer='Use date_diff().'" in output

    def test_reference_answer_omitted_when_output_has_none(self):
        dataset = _FakeDataset([_foreign_example("q")])
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-docs")

        assert "reference_answer" not in output

    def test_multiple_foreign_examples_each_get_a_snippet(self):
        dataset = _FakeDataset(
            [_foreign_example("first question"), _foreign_example("second question")]
        )
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-docs")

        assert output.count("_register_docs_case(") == 2


class TestExportForeignExamplesOtherDatasets:
    def test_non_docs_dataset_emits_commented_json_block(self):
        dataset = _FakeDataset([_foreign_example("a database question")])
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-database")

        assert "_register_docs_case" not in output
        assert "a database question" in output
        assert all(
            line.startswith("#") or not line.strip()
            for line in output.strip().splitlines()
        )

    def test_non_docs_dataset_notes_manual_scenario_and_checks(self):
        dataset = _FakeDataset([_foreign_example("a database question")])
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-database")

        assert "scenario" in output.lower()
        assert "checks" in output.lower()
        assert "by hand" in output.lower()

    def test_no_foreign_examples_reports_nothing_to_export(self):
        dataset = _FakeDataset([_code_owned_example("db/case-1")])
        client = _FakeClient(dataset)

        output = export_foreign_examples(client, "kuma-database")

        assert "No UI-added examples" in output


@pytest.mark.django_db
class TestExportAssistantEvalsCommand:
    def test_defaults_to_kuma_docs_and_prints_to_stdout(self, capsys):
        with (
            patch(
                "baserow_enterprise.management.commands.export_assistant_evals.load_all"
            ),
            patch(
                "baserow_enterprise.management.commands.export_assistant_evals."
                "get_phoenix_client"
            ),
            patch(
                "baserow_enterprise.management.commands.export_assistant_evals."
                "export_foreign_examples",
                return_value="# a snippet\n",
            ) as mock_export,
        ):
            call_command("export_assistant_evals")

        mock_export.assert_called_once()
        assert mock_export.call_args.args[1] == "kuma-docs"
        assert "# a snippet" in capsys.readouterr().out

    def test_dataset_option_is_forwarded(self):
        with (
            patch(
                "baserow_enterprise.management.commands.export_assistant_evals.load_all"
            ),
            patch(
                "baserow_enterprise.management.commands.export_assistant_evals."
                "get_phoenix_client"
            ),
            patch(
                "baserow_enterprise.management.commands.export_assistant_evals."
                "export_foreign_examples",
                return_value="# a snippet\n",
            ) as mock_export,
        ):
            call_command("export_assistant_evals", "--dataset", "kuma-database")

        assert mock_export.call_args.args[1] == "kuma-database"

    def test_out_option_writes_to_file(self, tmp_path):
        out_file = tmp_path / "snippets.py"
        with (
            patch(
                "baserow_enterprise.management.commands.export_assistant_evals.load_all"
            ),
            patch(
                "baserow_enterprise.management.commands.export_assistant_evals."
                "get_phoenix_client"
            ),
            patch(
                "baserow_enterprise.management.commands.export_assistant_evals."
                "export_foreign_examples",
                return_value="# a snippet\n",
            ),
        ):
            call_command(
                "export_assistant_evals",
                "--dataset",
                "kuma-docs",
                "--out",
                str(out_file),
            )

        assert out_file.read_text() == "# a snippet\n"
