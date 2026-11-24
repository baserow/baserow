from django.core.management.base import BaseCommand

from azure.core.exceptions import ResourceNotFoundError
from PIL import Image

from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_files.models import UserFile


class Command(BaseCommand):
    help = (
        "Regenerates all the user file thumbnails based on the current settings. "
        "Existing files will be overwritten."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "name",
            type=str,
            nargs="?",
            help="The name of the thumbnails to regenerate (tiny, small or card_cover).",
            default=None,
        )

    def handle(self, *args, **options):
        """
        Regenerates the thumbnails of all image user files. If the USER_THUMBNAILS
        setting ever changes then this file can be used to fix all the thumbnails.
        """

        handler = UserFileHandler()
        storage = get_default_storage()
        queryset = UserFile.objects.filter(
            is_image=True, deleted_at__isnull=True
        ).order_by("id")
        regenerated = 0
        last_id = 0

        while user_files := list(queryset.filter(id__gt=last_id)[:100]):
            last_id = user_files[-1].id
            for user_file in user_files:
                full_path = handler.user_file_path(user_file)
                try:
                    stream = storage.open(full_path)
                except FileNotFoundError:
                    continue

                try:
                    image = Image.open(stream)
                    handler.generate_and_save_image_thumbnails(
                        image,
                        user_file,
                        storage=storage,
                        only_with_name=options["name"],
                    )
                    image.close()
                    regenerated += 1
                except (IOError, ResourceNotFoundError):
                    pass

                stream.close()

        self.stdout.write(
            self.style.SUCCESS(f"{regenerated} thumbnails have been regenerated.")
        )
