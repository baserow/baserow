from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from baserow_enterprise.assistant.evals.models import DEFAULT_EVAL_MODEL
from baserow_enterprise.assistant.evals.phoenix import get_phoenix_client
from baserow_enterprise.assistant.evals.registry import get_case, load_all
from baserow_enterprise.assistant.evals.run import run_experiment_for
from baserow_enterprise.assistant.telemetry import setup_instrumentation


class Command(BaseCommand):
    help = "Run assistant eval experiments against Phoenix."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--dataset",
            default=None,
            help="Phoenix dataset name. Required unless --case is given.",
        )
        parser.add_argument(
            "--case",
            dest="case_ids",
            action="append",
            default=None,
            help="Eval case id to run (repeatable). Omit to run the whole dataset.",
        )
        parser.add_argument("--model", default=DEFAULT_EVAL_MODEL)
        parser.add_argument("--runs", type=int, default=1)
        parser.add_argument(
            "--name", dest="experiment_name", default=None, help="Experiment name."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dataset_name = options["dataset"]
        case_ids = options["case_ids"]
        if not dataset_name and not case_ids:
            raise CommandError("--dataset is required unless --case is given.")

        setup_instrumentation()
        load_all()

        if not dataset_name:
            # Cases carry their own dataset, so --case alone can resolve it.
            datasets = {get_case(case_id).dataset for case_id in case_ids}
            if len(datasets) > 1:
                raise CommandError(
                    f"--case values span multiple datasets ({sorted(datasets)}); "
                    "pass --dataset explicitly."
                )
            dataset_name = datasets.pop()

        result = run_experiment_for(
            dataset_name=dataset_name,
            model=options["model"],
            case_ids=case_ids,
            runs=options["runs"],
            experiment_name=options["experiment_name"],
        )

        self.stdout.write(self.style.SUCCESS(f"Experiment complete: {result}"))

        experiment_id = result.get("experiment_id") or result.get("id")
        dataset_id = result.get("dataset_id")
        if experiment_id and dataset_id:
            url = get_phoenix_client().experiments.get_experiment_url(
                dataset_id=dataset_id, experiment_id=experiment_id
            )
            self.stdout.write(f"Phoenix UI: {url}")
