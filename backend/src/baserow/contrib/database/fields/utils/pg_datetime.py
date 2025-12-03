import typing

from baserow.core.psycopg import is_psycopg3, psycopg

if is_psycopg3:
    from django.db.backends.signals import connection_created

    from baserow.core.psycopg import (
        DataError,
        DateBinaryLoader,
        DateLoader,
        TimestampBinaryLoader,
        TimestampLoader,
        TimestamptzBinaryLoader,
        TimestamptzLoader,
    )

    class _DateOverflowLoaderMixin:
        def load(self, data):
            try:
                return super().load(data)
            except DataError:
                return None

    class _TimestamptzOverflowLoaderMixin:
        timezone = None

        def load(self, data):
            try:
                res = super().load(data)
                return res.replace(tzinfo=self.timezone)
            except DataError:
                return None

    class BaserowDateLoader(_DateOverflowLoaderMixin, DateLoader):
        pass

    class BaserowDateBinaryLoader(_DateOverflowLoaderMixin, DateBinaryLoader):
        pass

    class BaserowTimestampLoader(_DateOverflowLoaderMixin, TimestampLoader):
        pass

    class BaserowTimestampBinaryLoader(_DateOverflowLoaderMixin, TimestampBinaryLoader):
        pass

    def pg_init():
        """
        Registers loaders for psycopg3 to handle date overflow.
        """

        psycopg.adapters.register_loader("date", BaserowDateLoader)
        psycopg.adapters.register_loader("date", BaserowDateBinaryLoader)

        psycopg.adapters.register_loader("timestamp", BaserowTimestampLoader)
        psycopg.adapters.register_loader("timestamp", BaserowTimestampBinaryLoader)

        # psycopg3 and timezones allow per-connection / per-cursor adapting. This is
        # done in django/db/backends/postgresql/psycopg_any.py in a hook that
        # registries tz aware adapter for each connection/cursor.
        # We can re-register our loaders here, but note that this will work on
        # per-connection tz setting. Cursors still will use django-provided adapters
        def register_context(signal, sender, connection, **kwargs):
            register_on_connection(connection)

        connection_created.connect(register_context)

    def register_on_connection(connection):
        """
        Registers timestamptz pg type loaders for a connection.
        """

        ctx = connection.connection.adapters

        class SpecificTzLoader(_TimestamptzOverflowLoaderMixin, TimestamptzLoader):
            timezone = connection.timezone

        class SpecificTzBinaryLoader(
            _TimestamptzOverflowLoaderMixin, TimestamptzBinaryLoader
        ):
            timezone = connection.timezone

        ctx.register_loader("timestamptz", SpecificTzLoader)
        ctx.register_loader("timestamptz", SpecificTzBinaryLoader)

else:
    from django.db.utils import DataError as DjangoDataError

    from psycopg2._psycopg import (
        DATE,
        DATEARRAY,
        DATETIME,
        DATETIMEARRAY,
        DATETIMETZ,
        DATETIMETZARRAY,
        DataError,
    )

    def _make_adapter(
        type_adapter,
    ) -> typing.Callable[[typing.Any, typing.Any], typing.Any]:
        def adapter(value, cur):
            try:
                return type_adapter(value, cur)
            except (DataError, DjangoDataError, ValueError):
                return

        return adapter

    def pg_init():
        """
        Registers loaders for psycopg2 to handle date overflow.
        """

        for type_adapter, typea_adapter in (
            (
                DATE,
                DATEARRAY,
            ),
            (
                DATETIME,
                DATETIMEARRAY,
            ),
            (
                DATETIMETZ,
                DATETIMETZARRAY,
            ),
        ):
            oid = type_adapter.values
            array_oid = typea_adapter.values
            typename = type_adapter.name
            handler = _make_adapter(type_adapter)
            array_handler = _make_adapter(typea_adapter)

            ptype = psycopg.extensions.new_type(oid, typename, handler)
            array_ptype = psycopg.extensions.new_type(
                array_oid, typename, array_handler
            )
            psycopg.extensions.register_type(ptype)
            psycopg.extensions.register_type(array_ptype)
