from collections import Counter

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F, TextField
from django.db.models.functions import Cast

from baserow.core.encryption import (
    DecryptionError,
    decrypt,
    encrypted_prefix,
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
        ring = get_key_ring()
        failed = 0
        for model, field in encrypted_fields():
            counts = self._count(model, field, ring)
            label = f"{model._meta.label}.{field.name}"
            summary = ", ".join(f"{key}: {n}" for key, n in sorted(counts.items()))
            self.stdout.write(f"{label}: {summary or 'empty'}")
            if not options["check"]:
                done, skipped = self._reencrypt(
                    model, field, ring.primary_id, options["batch_size"]
                )
                failed += skipped
                self.stdout.write(f"{label}: re-encrypted {done}")
        if failed:
            raise CommandError(
                f"{failed} secrets can't be decrypted and still use their old key. "
                "Keep that key in BASEROW_ENCRYPTION_KEY_FALLBACKS."
            )

    def _raw(self, model, field):
        # Cast to plain text, so the stored value is read as is.
        return model._base_manager.annotate(_raw=Cast(F(field.attname), TextField()))

    def _count(self, model, field, ring) -> Counter:
        counts = Counter()
        rows = self._raw(model, field).exclude(_raw="").exclude(_raw__isnull=True)
        for raw in rows.values_list("_raw", flat=True).iterator():
            key_id = get_key_id(raw)
            if key_id is not None and key_id not in ring.keys:
                counts[f"{key_id} (missing key)"] += 1
            else:
                counts[key_id or PLAIN_TEXT] += 1
        return counts

    def _reencrypt(self, model, field, primary_id, batch_size) -> tuple[int, int]:
        """
        :return: How many values were re-encrypted, and how many couldn't be
            decrypted.
        """

        done = failed = 0
        last_pk = None
        while True:
            with transaction.atomic():
                # Waits for rows that are being written instead of skipping
                # them, because the cursor below never comes back to a row.
                rows = (
                    self._raw(model, field)
                    .exclude(_raw="")
                    .exclude(_raw__isnull=True)
                    .exclude(_raw__startswith=encrypted_prefix(primary_id))
                    .order_by("pk")
                    .select_for_update(of=("self",))
                )
                if last_pk is not None:
                    rows = rows.filter(pk__gt=last_pk)
                batch = list(rows.values_list("pk", "_raw")[:batch_size])
                if not batch:
                    return done, failed
                last_pk = batch[-1][0]
                updates = []
                for pk, raw in batch:
                    try:
                        value = decrypt(raw, field.context) if get_key_id(raw) else raw
                    except DecryptionError as exc:
                        self.stderr.write(f"{model._meta.label} {pk}: {exc}")
                        failed += 1
                        continue
                    updates.append(model(pk=pk, **{field.attname: value}))
                model._base_manager.bulk_update(updates, [field.attname])
                done += len(updates)
