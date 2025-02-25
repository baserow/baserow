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

    # sentinel
    class DateOverflowPlaceholder:
        INVALID_DATE = "infinity"

        def isoformat(self):
            return self.INVALID_DATE

        def for_json(self):
            return self.INVALID_DATE

        def __str__(self):
            return self.INVALID_DATE

        def __cmp__(self, other):
            return isinstance(other, self.__class__) or self.INVALID_DATE == other

    DATE_OVERFLOW = DateOverflowPlaceholder()

    class _DateOverflowLoaderMixin:
        def load(self, data):
            try:
                return super().load(data)
            except DataError:
                return DATE_OVERFLOW

    class _TimestamptzOverflowLoaderMixin:
        timezone = None

        def load(self, data):
            try:
                res = super().load(data)
                return res.replace(tzinfo=self.timezone)
            except DataError:
                return DATE_OVERFLOW

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

        :return:
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

        :param connection:
        :return:
        """

        ctx = connection.connection.adapters

        class SpecificTzLoader(_TimestamptzOverflowLoaderMixin, TimestamptzLoader):
            timezone = connection.timezone

        class SpecificTzBinaryLoader(
            _TimestamptzOverflowLoaderMixin, TimestamptzBinaryLoader
        ):
            timezone = connection.timezone

        ctx.adapters.register_loader("timestamptz", SpecificTzLoader)
        ctx.adapters.register_loader("timestamptz", SpecificTzBinaryLoader)
