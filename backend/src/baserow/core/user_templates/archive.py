"""
Archives of user template revisions, built on the first download, in
`template-archives/<revision id>/<stamp>_<random>.zip`. The stamp makes them stale
after an upgrade.
"""

import hashlib
import re
import uuid
from os.path import join
from typing import Iterable

from django.core.cache import cache
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Count, Max

from baserow.core.storage import get_default_storage
from baserow.version import VERSION

TEMPLATE_ARCHIVES_DIRECTORY = "template-archives"
TEMPLATE_ARCHIVE_DIR_REGEX = re.compile(rf"^{TEMPLATE_ARCHIVES_DIRECTORY}/\d+/$")
TEMPLATE_ARCHIVE_STAMP_CACHE_KEY = "user_template_archive_stamp"
TEMPLATE_ARCHIVE_STAMP_LENGTH = 12


def _template_archive_stamp_cache_key() -> str:
    # A new version is a new key, so that a cache that wasn't cleared after an
    # upgrade can't hand out the stamp of the previous version.
    return f"{TEMPLATE_ARCHIVE_STAMP_CACHE_KEY}:{VERSION}"


def _has_migrations_table() -> bool:
    # Tests create the database without migrations. Cheaper than
    # `MigrationRecorder.has_table`, which lists every table.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT to_regclass(%s) IS NOT NULL",
            [MigrationRecorder.Migration._meta.db_table],
        )
        return cursor.fetchone()[0]


def get_template_archive_stamp() -> str:
    """
    Returns what identifies the version of this instance that builds the archives:
    a short hash of the Baserow version and of the applied migrations, so that an
    upgrade, or a migration applied without a new version, makes the archives built
    before stale. It's cached until the next migration, see
    `clear_template_archive_stamp`.

    :return: A string of hexadecimal characters.
    """

    key = _template_archive_stamp_cache_key()
    stamp = cache.get(key)
    if stamp is None:
        migrations = (
            MigrationRecorder.Migration.objects.aggregate(
                count=Count("id"), max_id=Max("id")
            )
            if _has_migrations_table()
            else {"count": 0, "max_id": None}
        )
        value = f"{VERSION}:{migrations['count']}:{migrations['max_id']}"
        stamp = hashlib.sha256(value.encode("utf-8")).hexdigest()[
            :TEMPLATE_ARCHIVE_STAMP_LENGTH
        ]
        cache.set(key, stamp, timeout=None)
    return stamp


def clear_template_archive_stamp(*args, **kwargs) -> None:
    """
    Clears the cached stamp, so that the next one counts the migrations just
    applied. It's connected to `post_migrate`.
    """

    cache.delete(_template_archive_stamp_cache_key())


def template_archive_dir(revision_id: int) -> str:
    """Returns the directory holding the archives of a revision."""

    return f"{TEMPLATE_ARCHIVES_DIRECTORY}/{revision_id}/"


def new_template_archive_name(revision_id: int) -> str:
    """Returns a name for a new archive of a revision, stamped with this version."""

    return (
        f"{template_archive_dir(revision_id)}"
        f"{get_template_archive_stamp()}_{uuid.uuid4().hex}.zip"
    )


def is_valid_template_archive(revision_id: int, name: str) -> bool:
    """
    Whether the archive can be handed out for the revision: it was built for this
    revision by the current version, and the file exists. An archive of another
    revision is never valid, even when a revision that only changed the details
    refers to it.
    """

    prefix = f"{template_archive_dir(revision_id)}{get_template_archive_stamp()}_"
    return name.startswith(prefix) and get_default_storage().exists(name)


def has_valid_archive(revision) -> bool:
    """
    Whether the stored archive of a revision can be handed out, see
    `is_valid_template_archive`.

    :param revision: The revision of a user template.
    """

    return is_valid_template_archive(revision.id, revision.archive.name or "")


def delete_template_archive_file(name: str) -> None:
    """Deletes an archive file. One that is gone already counts as deleted."""

    storage = get_default_storage()
    if storage.exists(name):
        storage.delete(name)


def delete_template_archives(directory: str, keep: Iterable[str] = ()) -> None:
    """
    Deletes the archives in the directory of a revision, except the ones in `keep`
    and the ones a template still refers to. The directory itself is removed once
    it's empty, where the storage has directories. A directory that is gone
    already counts as deleted, so deleting twice does nothing.

    :param directory: The directory of a revision, see `template_archive_dir`.
    :param keep: The names of the archives to keep.
    :raises ValueError: If the directory isn't the one of a revision.
    """

    from baserow.core.models import Template

    if not TEMPLATE_ARCHIVE_DIR_REGEX.fullmatch(directory):
        raise ValueError(f"{directory} isn't the directory of a template revision.")

    storage = get_default_storage()
    try:
        directories, files = storage.listdir(directory)
    except FileNotFoundError:
        return

    names = {join(directory, file_name) for file_name in files}
    kept = (
        set(keep)
        | set(
            Template.objects.filter(archive__in=names).values_list("archive", flat=True)
        )
    ) & names
    for name in names - kept:
        delete_template_archive_file(name)

    if not directories and not kept and storage.exists(directory):
        storage.delete(directory)
