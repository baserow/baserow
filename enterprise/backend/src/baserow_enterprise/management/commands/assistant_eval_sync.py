from django.core.management.base import BaseCommand

from baserow_enterprise.assistant.evals.phoenix import get_phoenix_client
from baserow_enterprise.assistant.evals.prompt_sync import sync_prompts
from baserow_enterprise.assistant.evals.registry import load_all
from baserow_enterprise.assistant.evals.sync import sync_datasets


class Command(BaseCommand):
    help = "Sync the assistant eval datasets and prompts to Phoenix."

    def handle(self, *args, **options):
        load_all()
        client = get_phoenix_client()
        counts = sync_datasets(client)

        for dataset_name, count in sorted(counts.items()):
            self.stdout.write(self.style.SUCCESS(f"{dataset_name}: {count} examples"))

        prompt_results = sync_prompts(client)
        for identifier, status in sorted(prompt_results.items()):
            self.stdout.write(self.style.SUCCESS(f"prompt {identifier}: {status}"))
