from argparse import ArgumentTypeError
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
MISSING_KEY = "missing key"
UNREADABLE = "can't be decrypted"


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise ArgumentTypeError("must be at least 1")
    return number


def encrypted_fields():
    for model in apps.get_models():
        for field in model._meta.concrete_fields:
            if isinstance(field, EncryptedTextField) and field.model is model:
                yield model, field


class Command(BaseCommand):
    help = (
        "Encrypts every stored secret with the current BASEROW_ENCRYPTION_KEY, "
        "including plain text written before it was encrypted. Run it after "
        "changing the key, then remove the old key from the fallbacks. Every "
        "stored secret is decrypted first, and the command fails when any of "
        "them can't be."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Only decrypt every secret and count them by the key that "
            "encrypted them. Fails when any of them can't be decrypted.",
        )
        parser.add_argument("--batch-size", type=positive_int, default=500)

    def handle(self, *args, **options):
        ring = get_key_ring()
        unreadable = 0
        reencrypt_failed = 0
        for model, field in encrypted_fields():
            counts, field_unreadable = self._count(model, field, ring)
            label = f"{model._meta.label}.{field.name}"
            summary = ", ".join(f"{key}: {n}" for key, n in sorted(counts.items()))
            self.stdout.write(f"{label}: {summary or 'empty'}")
            unreadable += field_unreadable
            if not options["check"]:
                done, skipped = self._reencrypt(
                    model, field, ring.primary_id, options["batch_size"]
                )
                reencrypt_failed += skipped
                self.stdout.write(f"{label}: re-encrypted {done}")
        failed = max(unreadable, reencrypt_failed)
        if failed:
            raise CommandError(
                f"{failed} secrets can't be decrypted. Keep the key that "
                "encrypted them in BASEROW_ENCRYPTION_KEY_FALLBACKS, or enter "
                "them again."
            )

    def _raw(self, model, field):
        # Cast to plain text, so the stored value is read as is.
        return model._base_manager.annotate(_raw=Cast(F(field.attname), TextField()))

    def _count(self, model, field, ring) -> tuple[Counter, int]:
        """
        Decrypts every stored value, so a value is only counted for its key
        when that key really reads it.

        :return: The number of values by key, and how many can't be decrypted.
        """

        counts = Counter()
        unreadable = 0
        rows = self._raw(model, field).exclude(_raw="").exclude(_raw__isnull=True)
        for pk, raw in rows.values_list("pk", "_raw").iterator():
            key_id = get_key_id(raw)
            if key_id is None:
                counts[PLAIN_TEXT] += 1
            elif key_id not in ring.keys:
                counts[f"{key_id} ({MISSING_KEY})"] += 1
                unreadable += 1
                self.stderr.write(f"{model._meta.label} {pk}: key {key_id} missing")
            else:
                try:
                    decrypt(raw, field.context)
                except DecryptionError as exc:
                    counts[f"{key_id} ({UNREADABLE})"] += 1
                    unreadable += 1
                    self.stderr.write(f"{model._meta.label} {pk}: {exc}")
                else:
                    counts[key_id] += 1
        return counts, unreadable

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
