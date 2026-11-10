from collections import Counter

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F, TextField
from django.db.models.functions import Cast

from baserow.core.encryption import (
    DecryptionError,
    decrypt,
    get_key_id,
    get_key_ring,
)
from baserow.core.fields import EncryptedTextField

PLAIN_TEXT = "plain text"


def encrypted_fields():
    for model in apps.get_models():
        for field in model._meta.concrete_fields:
            if isinstance(field, EncryptedTextField) and field.model is model:
                yield model, field


class Command(BaseCommand):
    help = (
        "Encrypts every stored secret with the current BASEROW_ENCRYPTION_KEY, "
        "including plain text written before it was encrypted. Run it after "
        "changing the key, then remove the old key from the fallbacks."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Only count the secrets by the key that encrypted them.",
        )
        parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *args, **options):
        primary_id = get_key_ring().primary_id
        for model, field in encrypted_fields():
            counts = self._count(model, field)
            label = f"{model._meta.label}.{field.name}"
            summary = ", ".join(f"{key}: {n}" for key, n in sorted(counts.items()))
            self.stdout.write(f"{label}: {summary or 'empty'}")
            if not options["check"]:
                done = self._reencrypt(model, field, primary_id, options["batch_size"])
                self.stdout.write(f"{label}: re-encrypted {done}")

    def _raw(self, model, field):
        # Cast to plain text, so the stored value is read as is.
        return model._base_manager.annotate(_raw=Cast(F(field.attname), TextField()))

    def _count(self, model, field) -> Counter:
        counts = Counter()
        rows = self._raw(model, field).exclude(_raw="").exclude(_raw__isnull=True)
        for raw in rows.values_list("_raw", flat=True).iterator():
            key_id = get_key_id(raw)
            if key_id is not None and key_id not in get_key_ring().keys:
                counts[f"{key_id} (missing key)"] += 1
            else:
                counts[key_id or PLAIN_TEXT] += 1
        return counts

    def _reencrypt(self, model, field, primary_id, batch_size) -> int:
        done = 0
        last_pk = None
        while True:
            with transaction.atomic():
                rows = (
                    self._raw(model, field)
                    .exclude(_raw="")
                    .exclude(_raw__isnull=True)
                    .exclude(_raw__startswith=f"enc:v1:{primary_id}:")
                    .order_by("pk")
                    .select_for_update(of=("self",), skip_locked=True)
                )
                if last_pk is not None:
                    rows = rows.filter(pk__gt=last_pk)
                batch = list(rows.values_list("pk", "_raw")[:batch_size])
                if not batch:
                    return done
                context = field._context()
                for pk, raw in batch:
                    last_pk = pk
                    try:
                        value = decrypt(raw, context) if get_key_id(raw) else raw
                    except DecryptionError as exc:
                        self.stderr.write(f"{model._meta.label} {pk}: {exc}")
                        continue
                    model._base_manager.filter(pk=pk).update(**{field.attname: value})
                    done += 1
