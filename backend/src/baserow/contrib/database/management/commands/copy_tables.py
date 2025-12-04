import math

# See comment below about nosec here.
from subprocess import Popen  # nosec
from typing import Any, Callable, Dict

from django.core.management.base import BaseCommand
from django.db import connections


def run(command, env):
    # Ignoring as this is a CLI admin tool calling Popen, we don't need to worry about
    # shell injection as to call this tool you must already have shell access...
    proc = Popen(command, shell=True, env=env)  # noqa: S602
    proc.wait()


def connection_string_from_django_connection(django_connection):
    settings_dict = django_connection.settings_dict
    params = [
        "-h " + settings_dict["HOST"],
        "-d " + settings_dict["NAME"],
        "-p " + settings_dict["PORT"],
        "-U " + settings_dict["USER"],
        "-w",  # Specify the password is not to be provided interactively as we are
        # setting the PGPASSWORD env variable instead.
    ]
    return " ".join(params)


def copy_tables(
    batch_size: int,
    dry_run: bool,
    ssl: bool,
    source_connection,
    target_connection,
    logger: Callable[[str], None],
    command_runner: Callable[[str, Dict[str, Any]], None],
):
    """
    Copies all tables from the database pointed at by `source_connection` to the
    database pointed at by `target_connection`. Does so in batches of `batch_size`
    tables to avoid shared memory errors due to not being able to lock all the tables at
    once in big databases.

    :param batch_size: How many tables to copy in each batch
    :param dry_run: When true only prints the commands it will run and won't actually
        run execute anything.
    :param ssl: When true configures psql/pg_dump to connect with sslmode=require .
    :param source_connection: A django connection wrapper pointing at the database you
        wish to copy all tables from.
    :param target_connection: A django connection wrapper pointing at the database you
        want to copy tables to.
    :type logger: A function which will be used to log info.
    :type command_runner: A function which executes a single bash command with the
        provided env dict.
    """

    source_connection_params = connection_string_from_django_connection(
        source_connection
    )
    target_connection_params = connection_string_from_django_connection(
        target_connection
    )

    target_tables_set = set(target_connection.introspection.table_names())
    target_db_name = target_connection.settings_dict["NAME"]

    source_tables = source_connection.introspection.table_names()
    source_db_name = source_connection.settings_dict["NAME"]

    if dry_run:
        logger(
            "Dry run... If --actually-run was provided then would"
            f" copy {source_db_name} to {target_db_name}"
        )
    else:
        logger(
            f"REAL RUN, ABOUT TO COPY TABLES FROM {source_db_name} to {target_db_name}"
        )
    if ssl:
        logger("Running with sslmode=require")
    count = 0
    num_batches = math.ceil(len(source_tables) / batch_size)
    logger(f"Importing {num_batches} batches of tables separately.")
    for batch_num in range(num_batches):
        batch = source_tables[batch_num * batch_size : (batch_num + 1) * batch_size]
        num_to_copy = 0
        table_str = ""
        for table in batch:
            if table not in target_tables_set:
                table_str += f" -t public.{table}"
                num_to_copy += 1
            else:
                logger(f"Skipping {table} as it is already in the target db")

        if num_to_copy > 0:
            count += num_to_copy
            logger(f"Importing {num_to_copy} tables in one go")
            command = (
                f"pg_dump {source_connection_params}{table_str} | "
                f"psql {target_connection_params}"
            )
            if dry_run:
                logger(f"Would have run {command}")
            else:
                password = source_connection.settings_dict["PASSWORD"]
                env = {"PGPASSWORD": password}
                if ssl:
                    env["PGSSLMODE"] = "require"
                logger(f"Running command: {command}")
                command_runner(
                    command,
                    env,
                )
        else:
            logger(
                f"Skipping import of batch {batch_num} as all tables were "
                "already in the target database."
            )
    logger(f"Successfully copied {count} tables.")


class Command(BaseCommand):
    help = "Copies all the tables from one django database connection to another."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source_connection",
            type=str,
            required=True,
            help="The django database connection name to copy tables from the public "
            "schema.",
        )
        parser.add_argument(
            "--target_connection",
            type=str,
            required=True,
            help="The django database connection name to copy tables to the public "
            "schema.",
        )
        parser.add_argument(
            "--batch_size",
            type=int,
            required=True,
            help="The number of tables to transfer at once in each pg_dump batch.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Provide this flag to show a dry run report of the tables that would "
            "be copied without this flag.",
        )
        parser.add_argument(
            "--ssl",
            action="store_true",
            help="Provide this flag if ssl should be enabled via sslmode=require",
        )

    def handle(self, *args, **options):
        dry_run = "dry_run" in options and options["dry_run"]
        ssl = "ssl" in options and options["ssl"]
        batch_size = options["batch_size"]

        source = options["source_connection"]
        source_connection = connections[source]

        target = options["target_connection"]
        target_connection = connections[target]

        copy_tables(
            batch_size,
            dry_run,
            ssl,
            source_connection,
            target_connection,
            self.stdout.write,
            run,
        )
