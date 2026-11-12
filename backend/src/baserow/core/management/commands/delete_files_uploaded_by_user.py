from django.core.management.base import BaseCommand
from django.utils.timezone import now

from baserow.core.models import UserFile
from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler


class Command(BaseCommand):
    help = (
        "This command permanently deletes all the user files uploaded by the provided "
        "user. It deletes the files where the `uploaded_by` matches the given `user_id`. "
        "Please note that this could lead to a situation where a file is deleted that "
        "another user also uploaded, if it's exactly the same file and the original "
        "filename was the same."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "user_id",
            type=int,
            help="The ID of the user whose uploaded files should be permanently deleted.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip confirmation prompt and delete immediately.",
        )

    def handle(self, *args, **options):
        user_id = options["user_id"]
        skip_confirmation = options["yes"]

        storage = get_default_storage()
        handler = UserFileHandler()

        user_files = UserFile.objects.filter(
            uploaded_by_id=user_id, deleted_at__isnull=True
        )
        count = user_files.count()

        self.stdout.write(f"\nFound {count} file(s) uploaded by user ID {user_id}\n")

        if count == 0:
            return

        for user_file in user_files:
            self.stdout.write(
                f"- {user_file.name} ({user_file.size} bytes, "
                f"uploaded {user_file.uploaded_at})"
            )

        if not skip_confirmation:
            confirm = input(
                "\nAre you sure you want to permanently delete these files from storage? [y/N]: "
            )
            if confirm.lower() not in ["y", "yes"]:
                self.stdout.write(self.style.WARNING("Aborted by user."))
                return

        deleted_count = 0
        for user_file in user_files:
            try:
                file_path = handler.user_file_path(user_file)
                deleted_paths = handler.delete_user_file_from_storage(
                    user_file, storage
                )
                if file_path not in deleted_paths:
                    self.stdout.write(
                        self.style.WARNING(f"File not found in storage: {file_path}")
                    )
                for path in deleted_paths:
                    self.stdout.write(f"Deleted: {path}")

                user_file.deleted_at = now()
                user_file.save(update_fields=["deleted_at"])
                deleted_count += 1

            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Error deleting file {user_file.name}: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully deleted {deleted_count} file(s) for user ID {user_id}."
            )
        )
