import os
import sys
from random import choice, randint

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from faker import Faker
from tqdm import tqdm

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.tokens.handler import TokenHandler
from baserow.core.handler import CoreHandler, WorkspaceDoesNotExist
from baserow.core.management.utils import run_command_concurrently
from baserow.core.models import Workspace

from .fill_table_fields import fill_table_fields
from .fill_table_rows import fill_table_rows

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Fills a workspace with many databases, tables, fields and rows. "
        "Useful for quickly populating a database with random data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "user_id",
            type=int,
            help="The user owner of all the data.",
        )
        parser.add_argument(
            "--workspace_id",
            nargs="?",
            type=int,
            help="The workspace to create databases in. If the value is 0, then a new workspace will be created.",
            default=-1,
        )
        parser.add_argument(
            "--database-count",
            nargs="?",
            type=int,
            help="Amount of databases that need to be created.",
            default=10,
        )
        parser.add_argument(
            "--table-count",
            nargs="?",
            type=int,
            help="Amount of tables per database that need to be created.",
            default=20,
        )
        parser.add_argument(
            "--field-count",
            nargs="?",
            type=int,
            help="Amount of fields per table that need to be created on average (see percentage_variation).",
            default=30,
        )
        parser.add_argument(
            "--row-count",
            nargs="?",
            type=int,
            help="Amount of rows per table that need to be created on average (see percentage_variation).",
            default=1000,
        )
        parser.add_argument(
            "--token-count",
            nargs="?",
            type=int,
            help="Amount of tokens per database that need to be created on average (see percentage_variation).",
            default=1,
        )
        parser.add_argument(
            "--percentage-variation",
            nargs="?",
            type=int,
            help="The percentage variation that is allowed for the amount of tables, fields and rows.",
            default=0,
        )
        parser.add_argument(
            "--concurrency",
            nargs="?",
            type=int,
            help="How many concurrent processes should be used to create databases.",
            default=5,
        )

    def handle(self, *args, **options):
        user_id = options["user_id"]
        workspace_id = options["workspace_id"]
        database_count = options["database_count"]
        table_count = options["table_count"]
        field_count = options["field_count"]
        row_count = options["row_count"]
        token_count = options["token_count"]
        concurrency = options["concurrency"]
        percentage_variation = options["percentage_variation"]

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"The user with id {user_id} was not found.")
            )
            sys.exit(1)

        try:
            workspace = CoreHandler().get_workspace(workspace_id)
        except WorkspaceDoesNotExist:
            workspace = (
                CoreHandler().create_workspace(user, name=Faker().name()).workspace
            )
            print(f"Created workspace {workspace.name} with id: {workspace.id}")

        if concurrency == 1:
            fill_workspace_with_data(
                user,
                workspace,
                database_count,
                table_count,
                token_count,
                field_count,
                row_count,
                percentage_variation,
            )
        else:
            concurrency = min(concurrency, database_count)
            run_command_concurrently(
                [
                    "./baserow",
                    "fill_workspace",
                    str(user_id),
                    "--workspace_id",
                    str(workspace.id),
                    "--database-count",
                    str(max(1, int(database_count / concurrency))),
                    "--table-count",
                    str(table_count),
                    "--field-count",
                    str(field_count),
                    "--row-count",
                    str(row_count),
                    "--percentage-variation",
                    str(percentage_variation),
                    "--concurrency",
                    "1",
                ],
                concurrency,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{database_count} databases each with {table_count} tables have been created."
            )
        )


def fill_workspace_with_data(
    user,
    workspace: Workspace,
    database_count: int,
    table_count: int,
    token_count: int,
    avg_field_count: int,
    avg_row_count: int,
    percentage_variation: int = 0,
):
    process_id = os.getpid()
    faker = Faker()
    print(
        f"User {user.email} is going to make {database_count} databases "
        f"in workspace {workspace.name} in sub process {process_id}"
    )

    min_field_count = max(1, int(avg_field_count * (1 - percentage_variation / 100)))
    max_field_count = int(avg_field_count * (1 + percentage_variation / 100))
    min_row_count = max(1, int(avg_row_count * (1 - percentage_variation / 100)))
    max_row_count = int(avg_row_count * (1 + percentage_variation / 100))

    with tqdm(
        range(database_count * table_count + token_count),
        desc=f"Worker" f" {process_id}",
    ) as pbar:
        created_databases_and_tables = {}
        for _ in range(database_count):
            with transaction.atomic():
                database = (
                    CoreHandler()
                    .create_application(user, workspace, "database", name=faker.name())
                    .specific
                )
                created_databases_and_tables[database] = []
                print(f"Creating {table_count} tables in database {database.id}")
                for _ in range(table_count):
                    table, _ = TableHandler().create_table(
                        user, database, name=faker.name()
                    )
                    field_count = randint(min_field_count, max_field_count)  # nosec
                    print(
                        f"Creating {field_count} fields for table {table.id} from process {process_id}"
                    )
                    fill_table_fields(field_count, table)
                    row_count = randint(min_row_count, max_row_count)  # nosec
                    print(
                        f"Creating {row_count} rows for table {table.id} from process {process_id}"
                    )
                    fill_table_rows(row_count, table)
                    created_databases_and_tables[database].append(table)
                    pbar.update(1)
        for _ in range(token_count):
            with transaction.atomic():
                permissions = []
                for i in range(0, 4):
                    random = randint(0, 2)  # nosec
                    value = True
                    if random == 1:
                        value = False
                    if random == 2:
                        try:
                            database = choice(  # nosec
                                list(created_databases_and_tables.keys())
                            )
                            table = choice(  # nosec
                                created_databases_and_tables[database]
                            )
                            value = [database, table]
                        except IndexError:
                            value = False
                    permissions.append(value)

                token = TokenHandler().create_token(
                    user=user, workspace=workspace, name=f"Token {_}"
                )
                TokenHandler().update_token_permissions(
                    user=user,
                    token=token,
                    create=permissions[0],
                    read=permissions[1],
                    update=permissions[2],
                    delete=permissions[3],
                )
                pbar.update(1)
