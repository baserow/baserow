import sys

from django.core.management.base import BaseCommand

from baserow.core.trash.exceptions import PermanentDeletionMaxLocksExceededException
from baserow.core.trash.handler import TrashHandler


class Command(BaseCommand):
    help = "Deletes items from trash that had been marked to be permanently deleted"

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete-all",
            action="store_true",
            help="Delete all items from trash regardless of their marked status.",
        )

    def handle(self, *args, **options):
        delete_all = options.get("delete_all", False)
        try:
            if delete_all:
                TrashHandler().mark_all_trash_for_permanent_deletion()
            TrashHandler().permanently_delete_marked_trash()
        except PermanentDeletionMaxLocksExceededException as e:
            self.stdout.write(self.style.ERROR(e.message))
            sys.exit(1)
