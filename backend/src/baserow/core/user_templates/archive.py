"""
Archives of user template revisions, built on the first download, in
`template-archives/<revision id>/<stamp>_<random>.zip`. The stamp makes them stale
after an upgrade.
"""

import hashlib
import re
import uuid
from os.path import join
from typing import TYPE_CHECKING, Any

from django.core.cache import cache
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Count, Max
from django.utils.text import slugify

from baserow.core.context import clear_current_workspace_id, set_current_workspace_id
from baserow.core.storage import get_default_storage
from baserow.version import VERSION

if TYPE_CHECKING:
    from baserow.core.models import Template

TEMPLATE_ARCHIVES_DIRECTORY = "template-archives"
TEMPLATE_ARCHIVE_DIR_REGEX = re.compile(rf"^{TEMPLATE_ARCHIVES_DIRECTORY}/\d+/$")
TEMPLATE_ARCHIVE_STAMP_CACHE_KEY = "user_template_archive_stamp"
TEMPLATE_ARCHIVE_STAMP_LENGTH = 12


def _template_archive_stamp_cache_key() -> str:
    """
    Returns the cache key of the stamp. A new version is a new key, so that a
    cache that wasn't cleared after an upgrade can't hand out the stamp of the
    previous version.

    :return: The cache key.
    """

    return f"{TEMPLATE_ARCHIVE_STAMP_CACHE_KEY}:{VERSION}"


def _has_migrations_table() -> bool:
    """
    Whether the table of the applied migrations exists, which it doesn't when
    tests create the database without migrations. Cheaper than
    `MigrationRecorder.has_table`, which lists every table.

    :return: Whether the table exists.
    """

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


def clear_template_archive_stamp(*args: Any, **kwargs: Any) -> None:
    """
    Clears the cached stamp, so that the next one counts the migrations just
    applied. It's connected to `post_migrate`.

    :param args: The arguments of the signal, unused.
    :param kwargs: The keyword arguments of the signal, unused.
    """

    cache.delete(_template_archive_stamp_cache_key())


def template_archive_dir(revision_id: int) -> str:
    """
    Returns the directory holding the archives of a revision.

    :param revision_id: The id of the revision.
    :return: The name of the directory, which ends with a `/`.
    """

    return f"{TEMPLATE_ARCHIVES_DIRECTORY}/{revision_id}/"


def new_template_archive_name(revision_id: int) -> str:
    """
    Returns a name for a new archive of a revision, stamped with this version.

    :param revision_id: The id of the revision.
    :return: A name in the directory of the revision, see `template_archive_dir`.
    """

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

    :param revision_id: The id of the revision.
    :param name: The name of the stored archive.
    :return: Whether the archive can be handed out.
    """

    prefix = f"{template_archive_dir(revision_id)}{get_template_archive_stamp()}_"
    return name.startswith(prefix) and get_default_storage().exists(name)


def has_valid_archive(revision: "Template") -> bool:
    """
    Whether the stored archive of a revision can be handed out, see
    `is_valid_template_archive`.

    :param revision: The revision of a user template.
    :return: Whether the archive can be handed out.
    """

    return is_valid_template_archive(revision.id, revision.archive.name or "")


def template_archive_url(revision: "Template") -> str:
    """
    Returns the URL of the archive of a revision. The storage may sign it with the
    current workspace, so it's made with the workspace of the revision, which only
    the users who can open the template can open, see secure file serve.

    :param revision: A revision of a user template with a valid archive.
    :return: The URL of the archive.
    """

    try:
        set_current_workspace_id(revision.workspace_id)
        return get_default_storage().url(revision.archive.name)
    finally:
        clear_current_workspace_id()


def template_archive_file_name(revision: "Template") -> str:
    """
    Returns the name to save the archive of a revision as, from its name.

    :param revision: A revision of a user template.
    :return: The file name, `template.zip` when the name has no usable character.
    """

    return f"{slugify(revision.name) or 'template'}.zip"


def delete_template_archive_file(name: str) -> None:
    """
    Deletes an archive file. One that is gone already counts as deleted.

    :param name: The name of the stored archive.
    """

    storage = get_default_storage()
    if storage.exists(name):
        storage.delete(name)


def delete_template_archives(directory: str) -> None:
    """
    Deletes the archives in the directory of a revision, except the ones a
    template still refers to. The directory itself is removed once it's empty,
    where the storage has directories. A directory that is gone already counts as
    deleted, so deleting twice does nothing.

    :param directory: The directory of a revision, see `template_archive_dir`.
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
    kept = names & set(
        Template.objects.filter(archive__in=names).values_list("archive", flat=True)
    )
    for name in names - kept:
        delete_template_archive_file(name)

    if not directories and not kept and storage.exists(directory):
        storage.delete(directory)
