import operator
from collections import defaultdict
from datetime import datetime, timezone
from functools import reduce
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.db.models import Q, QuerySet

from loguru import logger
from rest_framework import serializers

from baserow.api.exceptions import RequestBodyValidationException
from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.field_types import (
    EmailFieldType,
    FormulaFieldType,
    LongTextFieldType,
    NumberFieldType,
    SingleSelectFieldType,
    TextFieldType,
    UUIDFieldType,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import FieldType
from baserow.contrib.database.rows.actions import CreateRowsActionType
from baserow.contrib.database.rows.operations import ReadDatabaseRowOperationType
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.app_auth_providers.handler import AppAuthProviderHandler
from baserow.core.formula.validator import ensure_string
from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.exceptions import UserNotFound
from baserow.core.user_sources.exceptions import UserSourceImproperlyConfigured
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.registries import UserSourceCount, UserSourceType
from baserow.core.user_sources.types import UserSourceDict
from baserow.core.user_sources.user_source_user import UserSourceUser
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowPasswordAppAuthProvider,
    LocalBaserowUserSource,
)


class LocalBaserowUserSourceType(UserSourceType):
    type = "local_baserow"
    model_class = LocalBaserowUserSource
    field_types_allowed_as_name = [
        EmailFieldType.type,
        TextFieldType.type,
        LongTextFieldType.type,
        NumberFieldType.type,
        UUIDFieldType.type,
    ]
    field_types_allowed_as_email = [
        EmailFieldType.type,
        TextFieldType.type,
        LongTextFieldType.type,
    ]
    # Please ensure this list is kept in sync with its frontend counterpart:
    # `userSourceTypes.js::LocalBaserowUserSourceType::allowedRoleFieldTypes`
    field_types_allowed_as_role = [
        TextFieldType.type,
        SingleSelectFieldType.type,
        FormulaFieldType.type,
    ]

    class SerializedDict(UserSourceDict):
        table_id: int
        email_field_id: int
        name_field_id: int
        role_field_id: int

    serializer_field_names = [
        "table_id",
        "email_field_id",
        "name_field_id",
        "role_field_id",
    ]
    allowed_fields = ["table", "email_field", "name_field", "role_field"]

    # A list of fields which the page designer must configure so
    # that the `LocalBaserowUserSource` is considered "configured".
    fields_to_configure = [
        "table",
        "name_field",
        "email_field",
        "integration",
    ]

    serializer_field_overrides = {
        "table_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text="The id of the Baserow table we want the data for.",
        ),
        "email_field_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text="The id of the field to use as email for the user account.",
        ),
        "name_field_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text="The id of the field that contains the user name.",
        ),
        "role_field_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text="The id of the field that contains the user role.",
        ),
    }

    def enhance_queryset(self, queryset):
        """
        Allow to enhance the queryset when querying the user_source mainly to improve
        performances.
        """

        return (
            super()
            .enhance_queryset(queryset)
            .select_related(
                "table__database__workspace",
                "role_field",
                "email_field",
                "name_field",
            )
        )

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[LocalBaserowUserSource] = None,
    ) -> Dict[str, Any]:
        """Load the table instance instead of the ID."""

        # We resolve the integration first
        values = super().prepare_values(values, user)

        if "table_id" in values:
            table_id = values.pop("table_id")
            if table_id is not None:
                try:
                    table = TableHandler().get_table(table_id)
                except TableDoesNotExist as exc:
                    raise RequestBodyValidationException(
                        {
                            "table_id": [
                                {
                                    "detail": f"The table with ID {table_id} doesn't "
                                    "exist",
                                    "code": "invalid_table",
                                }
                            ]
                        }
                    ) from exc

                # check that table belongs to same workspace
                integration_to_check = None
                if instance:
                    integration_to_check = instance.integration
                if "integration" in values:
                    integration_to_check = values["integration"]

                if (
                    not integration_to_check
                    or table.database.workspace_id
                    != integration_to_check.application.workspace_id
                ):
                    raise RequestBodyValidationException(
                        {
                            "table_id": [
                                {
                                    "detail": f"The table with ID {table.id} is not "
                                    "related to the given workspace.",
                                    "code": "invalid_table",
                                }
                            ]
                        }
                    )
                values["table"] = table

                # Reset the fields if the table has changed
                if (
                    "email_field_id" not in values
                    and instance
                    and instance.email_field_id
                    and instance.email_field.table_id != table_id
                ):
                    values["email_field_id"] = None

                if (
                    "name_field_id" not in values
                    and instance
                    and instance.name_field_id
                    and instance.name_field.table_id != table_id
                ):
                    values["name_field_id"] = None

                if (
                    "role_field_id" not in values
                    and instance
                    and instance.role_field_id
                    and instance.role_field.table_id != table_id
                ):
                    values["role_field_id"] = None
            else:
                values["table"] = None

        table_to_check = None

        if instance:
            table_to_check = instance.table
        if "table" in values:
            table_to_check = values["table"]

        if "email_field_id" in values:
            email_field_id = values.pop("email_field_id")
            if email_field_id is not None:
                if not table_to_check:
                    raise RequestBodyValidationException(
                        {
                            "email_field_id": [
                                {
                                    "detail": "Please select a table before selecting "
                                    "this field.",
                                    "code": "missing_table",
                                }
                            ]
                        }
                    )

                try:
                    field = FieldHandler().get_field(email_field_id)
                except FieldDoesNotExist as exc:
                    raise RequestBodyValidationException(
                        {
                            "email_field_id": [
                                {
                                    "detail": "The provided Id doesn't exist.",
                                    "code": "invalid_field",
                                }
                            ]
                        }
                    ) from exc

                if field.table_id != table_to_check.id:
                    raise RequestBodyValidationException(
                        {
                            "email_field_id": [
                                {
                                    "detail": f"The field with ID {email_field_id} is "
                                    "not related to the given table.",
                                    "code": "invalid_field",
                                }
                            ]
                        }
                    )
                if field.get_type().type not in self.field_types_allowed_as_email:
                    raise RequestBodyValidationException(
                        {
                            "email_field_id": [
                                {
                                    "detail": "This field type can't be used as "
                                    "email.",
                                    "code": "invalid_field",
                                }
                            ]
                        }
                    )

                values["email_field"] = field
            else:
                values["email_field"] = None

        if "name_field_id" in values:
            name_field_id = values.pop("name_field_id")
            if name_field_id is not None:
                if not table_to_check:
                    raise RequestBodyValidationException(
                        {
                            "name_field_id": [
                                {
                                    "detail": "Please select a table before selecting "
                                    "this field.",
                                    "code": "missing_table",
                                }
                            ]
                        }
                    )

                try:
                    field = FieldHandler().get_field(name_field_id)
                except FieldDoesNotExist as exc:
                    raise RequestBodyValidationException(
                        {
                            "name_field_id": [
                                {
                                    "detail": "The provided Id doesn't exist.",
                                    "code": "invalid_field",
                                }
                            ]
                        }
                    ) from exc

                if field.table_id != table_to_check.id:
                    raise RequestBodyValidationException(
                        {
                            "name_field_id": [
                                {
                                    "detail": f"The field with ID {name_field_id} is "
                                    "not related to the given table.",
                                    "code": "invalid_field",
                                }
                            ]
                        }
                    )

                if field.get_type().type not in self.field_types_allowed_as_name:
                    raise RequestBodyValidationException(
                        {
                            "name_field_id": [
                                {
                                    "detail": "This field type can't be used as "
                                    "name.",
                                    "code": "invalid_field",
                                }
                            ]
                        }
                    )

                values["name_field"] = field
            else:
                values["name_field"] = None

        if "role_field_id" in values:
            role_field_id = values.pop("role_field_id")
            if role_field_id is not None:
                if not table_to_check:
                    raise RequestBodyValidationException(
                        {
                            "role_field_id": [
                                {
                                    "detail": "Please select a table before selecting "
                                    "this field.",
                                    "code": "missing_table",
                                }
                            ]
                        }
                    )

                try:
                    field = FieldHandler().get_field(role_field_id)
                except FieldDoesNotExist as exc:
                    raise RequestBodyValidationException(
                        {
                            "role_field_id": [
                                {
                                    "detail": "The provided Id doesn't exist.",
                                    "code": "invalid_field",
                                }
                            ]
                        }
                    ) from exc

                if field.table_id != table_to_check.id:
                    raise RequestBodyValidationException(
                        {
                            "role_field_id": [
                                {
                                    "detail": f"The field with ID {role_field_id} is "
                                    "not related to the given table.",
                                    "code": "invalid_field",
                                }
                            ]
                        }
                    )

                if field.get_type().type not in self.field_types_allowed_as_role:
                    raise RequestBodyValidationException(
                        {
                            "role_field_id": [
                                {
                                    "detail": "This field type can't be used as "
                                    "a role.",
                                    "code": "invalid_field",
                                }
                            ]
                        }
                    )

                values["role_field"] = field
            else:
                values["role_field"] = None

        return values

    def after_update(
        self,
        user: AbstractUser,
        user_source: LocalBaserowUserSource,
        values: Dict[str, Any],
        trigger_user_count_update: bool = False,
    ):
        if "auth_provider" not in values and "table" in values:
            # We clear all auth provider when the table changes
            for ap in AppAuthProviderHandler.list_app_auth_providers_for_user_source(
                user_source
            ):
                ap.get_type().after_user_source_update(user, ap, user_source)

        return super().after_update(
            user, user_source, values, trigger_user_count_update
        )

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Dict[int, int]],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> Any:
        """
        Map table, email_field and name_field ids.
        """

        if value and "database_tables" in id_mapping and prop_name == "table_id":
            return id_mapping["database_tables"].get(value)

        if (
            value
            and "database_fields" in id_mapping
            and prop_name in ("email_field_id", "name_field_id", "role_field_id")
        ):
            return id_mapping["database_fields"].get(value)

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def get_user_model(self, user_source: LocalBaserowUserSource):
        if TrashHandler.item_has_a_trashed_parent(
            user_source.table, check_item_also=True
        ):
            # As we CASCADE when a table is deleted, the table shouldn't
            # exist only if it's trashed and not yet deleted.
            raise UserSourceImproperlyConfigured("The table doesn't exist.")

        table = user_source.table
        integration = user_source.integration

        integration = integration.get_specific(integration.get_type().enhance_queryset)

        app_auth_providers = (
            AppAuthProviderHandler.list_app_auth_providers_for_user_source(user_source)
        )

        providers_fields = [
            f
            for ap in app_auth_providers
            if hasattr(ap.get_type(), "get_user_model_field_ids")
            for f in ap.get_type().get_user_model_field_ids(ap)
        ]

        model = table.get_model(
            add_dependencies=False,
            field_ids=[
                f
                for f in [
                    user_source.email_field_id,
                    user_source.name_field_id,
                    user_source.role_field_id,
                    *providers_fields,
                ]
                if f
            ],
        )

        CoreHandler().check_permissions(
            integration.authorized_user,
            ReadDatabaseRowOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        return model

    def is_configured(
        self, user_source: LocalBaserowUserSource, raise_exception=False
    ) -> bool:
        """
        Returns True if the user source is configured properly. False otherwise.
        """

        for field in self.fields_to_configure:
            if (
                not getattr(user_source, f"{field}_id")
                or (
                    field == "table"  # We need to check the hierarchy only for table
                    and TrashHandler.item_has_a_trashed_parent(
                        getattr(user_source, field), check_item_also=True
                    )
                )
                or (field != "table" and getattr(user_source, field).trashed)
            ):
                if raise_exception:
                    raise UserSourceImproperlyConfigured(
                        f"The {field} field is not configured."
                    )
                else:
                    return False

        return True

    def gen_uid(self, user_source: LocalBaserowUserSource):
        """
        We want to invalidate user tokens if the table or the email field change.
        """

        return (
            f"{user_source.id}"
            f"_{user_source.table_id if user_source.table_id else '0'}"
            f"_{user_source.email_field_id if user_source.email_field_id else '0'}"
            f"_{user_source.role_field_id if user_source.role_field_id else '0'}"
        )

    def role_type_is_allowed(self, role_field: Optional[FieldType]) -> bool:
        """Return True if the Role Field's type is allowed, False otherwise."""

        if role_field is None:
            return False

        return role_field.get_type().type in self.field_types_allowed_as_role

    def get_user_role(self, user, user_source: LocalBaserowUserSource) -> str:
        """
        Return the User Role of the user if the role_field is defined.

        If the UserSource's role_field is null, return the Default User Role.
        """

        if self.role_type_is_allowed(user_source.role_field):
            field = getattr(user, user_source.role_field.db_column) or ""
            if user_source.role_field.get_type().can_have_select_options:
                return field.value.strip() if field else ""

            return ensure_string(field).strip()

        return self.get_default_user_role(user_source)

    def list_users(
        self, user_source: LocalBaserowUserSource, count: int = 5, search: str = ""
    ):
        """
        Returns the users from the table selected with the user source.
        """

        if not self.is_configured(user_source):
            return []

        try:
            UserModel = self.get_user_model(user_source)
        except UserSourceImproperlyConfigured:
            # The associated table has been trashed, we
            # have no generated table model to use.
            return []

        queryset = UserModel.objects.all()

        if search:
            search_mode = SearchHandler.get_default_search_mode_for_table(
                user_source.table
            )
            queryset = queryset.search_all_fields(search, search_mode=search_mode)

        return [
            UserSourceUser(
                user_source,
                user,
                user.id,
                getattr(user, user_source.name_field.db_column),
                getattr(user, user_source.email_field.db_column),
                self.get_user_role(user, user_source),
            )
            for user in queryset[:count]
        ]

    def get_roles(self, user_source: LocalBaserowUserSource) -> List[str]:
        """
        Given a UserSource, return all valid roles for it.

        If the UserSource's role_field is null, return a list with a single
        role that is the Default User Role.
        """

        if not user_source.role_field:
            return [self.get_default_user_role(user_source)]

        if user_source.role_field.get_type().can_have_select_options:
            return sorted(
                set(
                    user_source.role_field.select_options.values_list(
                        "value", flat=True
                    )
                )
            )

        if not self.role_type_is_allowed(user_source.role_field):
            return []

        try:
            table = TableHandler().get_table(user_source.role_field.table.id)
        except TableDoesNotExist:
            return []

        role_field_column = user_source.role_field.db_column

        roles = []
        for role in (
            table.get_model()
            .objects.filter(**{f"{role_field_column}__isnull": False})
            .distinct()
            .values_list(role_field_column, flat=True)
            .order_by(role_field_column)
        ):
            roles.append(ensure_string(role).strip())

        return roles

    def get_user(self, user_source: LocalBaserowUserSource, **kwargs):
        """
        Returns a user from the selected table.
        """

        try:
            UserModel = self.get_user_model(user_source)
        except UserSourceImproperlyConfigured as exc:
            raise UserNotFound() from exc

        user = None

        if not self.is_configured(user_source):
            raise UserNotFound()

        if kwargs.get("email", None):
            # As we have no unique constraint for fields we return the first matching
            # user.
            user = UserModel.objects.filter(
                **{f"{user_source.email_field.db_column}__iexact": kwargs["email"]}
            ).first()

        if kwargs.get("user_id", None):
            try:
                user = UserModel.objects.get(id=kwargs["user_id"])
            except UserModel.DoesNotExist as exc:
                raise UserNotFound() from exc

        if user:
            return UserSourceUser(
                user_source,
                user,
                user.id,
                getattr(user, f"field_{user_source.name_field_id}"),
                getattr(user, f"field_{user_source.email_field_id}"),
                self.get_user_role(user, user_source),
            )

        raise UserNotFound()

    def create_user(self, user_source: LocalBaserowUserSource, email, name, role=None):
        """
        Creates the user in the configured table.
        """

        self.is_configured(user_source, raise_exception=True)

        integration = user_source.integration.specific

        model = user_source.table.get_model()

        values = {
            user_source.name_field.db_column: name,
            user_source.email_field.db_column: email,
        }
        if role and user_source.role_field_id:
            values[user_source.role_field.db_column] = role

        try:
            # Use the action to keep track on what's going on
            (user,) = CreateRowsActionType.do(
                user=integration.authorized_user,
                table=user_source.table,
                rows_values=[values],
                model=model,
            )
        except Exception as e:
            logger.exception(e)
            raise UserSourceImproperlyConfigured("Error while creating the user") from e

        return UserSourceUser(
            user_source,
            user,
            user.id,
            getattr(user, user_source.name_field.db_column),
            getattr(user, user_source.email_field.db_column),
            self.get_user_role(user, user_source),
        )

    def authenticate(self, user_source: LocalBaserowUserSource, **kwargs):
        """
        Authenticates using the given credentials. It uses the password auth provider.
        """

        self.is_configured(user_source, raise_exception=True)

        try:
            # Get the unique password auth provider
            auth_provider = LocalBaserowPasswordAppAuthProvider.objects.get(
                user_source=user_source.id
            )
        except LocalBaserowPasswordAppAuthProvider.DoesNotExist as exc:
            raise UserSourceImproperlyConfigured() from exc

        if not auth_provider.get_type().is_configured(auth_provider):
            raise UserSourceImproperlyConfigured()

        return auth_provider.get_type().authenticate(
            auth_provider,
            kwargs.get("email", ""),
            kwargs.get("password", ""),
        )

    def _get_cached_user_count(
        self, user_source: LocalBaserowUserSource
    ) -> Optional[UserSourceCount]:
        """
        Given a `user_source`, return the cached user count if it exists.

        :param user_source: The `LocalBaserowUserSource` instance.
        :return: A `UserSourceCount` instance if the cached user count exists,
            otherwise `None`.
        """

        cached_value = cache.get(
            self._generate_update_user_count_cache_key(user_source)
        )
        if cached_value is not None:
            user_count, timestamp = cached_value.split("-")
            return UserSourceCount(
                count=int(user_count),
                last_updated=datetime.fromtimestamp(float(timestamp)),
            )
        return None

    def _generate_update_user_count_cache_key(
        self, user_source: LocalBaserowUserSource
    ) -> str:
        """
        Given a `user_source`, generate a cache key for the user count cache entry.

        :param user_source: The `LocalBaserowUserSource` instance.
        :return: A string representing the cache key.
        """

        return f"local_baserow_user_source_{user_source.id}_user_count"

    def _generate_update_user_count_cache_value(
        self, user_count: int, now: datetime = None
    ) -> str:
        """
        Given a `user_count`, generate a cache value for the user count cache entry.

        :param user_count: The user count integer.
        :param now: The datetime object representing the current time. If not provided,
            we will use the current datetime.
        :return: A string representing the cache value.
        """

        now = now or datetime.now(tz=timezone.utc)
        return f"{user_count}-{now.timestamp()}"

    def after_user_source_update_requires_user_recount(
        self,
        user_source: LocalBaserowUserSource,
        prepared_values: dict[str, Any],
    ) -> bool:
        """
        By default, the Local Baserow user source type will re-count
        its users following any change to the user source.

        :param user_source: the user source which is being updated.
        :param prepared_values: the prepared values which will be
            used to update the user source.
        :return: whether a re-count is required.
        """

        return True

    def update_user_count(
        self,
        user_sources: QuerySet[LocalBaserowUserSource] = None,
    ) -> Optional[UserSourceCount]:
        """
        Responsible for updating the cached number of users in this user source type.
        If `user_sources` are provided, we will only update the user count for those
        user sources. If no `user_sources` are provided, we will update the user count
        for all configured `LocalBaserowUserSource`.

        :param user_sources: If a queryset of user sources is provided, we will only
            update the user count for those user sources, otherwise we'll find all
            configured user sources and update their user counts.
        :return: if a `user_source` is provided, a `UserSourceCount is returned,
            otherwise we will return `None`.
        """

        # If no `user_sources` are provided, we will query for all "configured"
        # user sources, i.e. those that have all the required fields set.
        if not user_sources:
            field_q = reduce(
                operator.and_,
                (~Q(**{field: None}) for field in self.fields_to_configure),
            )
            user_sources = self.enhance_queryset(
                self.model_class.objects.select_related(
                    "integration__application__workspace"
                ).filter(field_q)
            )

        # Narrow down the `user_sources` to only those that pass our `is_configured`
        # check. Often this will be the same filtering as what is done in the ORM, but
        # just in case we have additional validation requirements in `is_configured`,
        # we will filter again here.
        configured_user_sources = [us for us in user_sources if self.is_configured(us)]

        # Fetch all the table records in bulk.
        user_source_table_map = defaultdict(list)
        for us in configured_user_sources:
            user_source_table_map[us.table_id].append(us)
        tables = TableHandler.get_tables().filter(id__in=user_source_table_map.keys())

        user_source_count = None
        for table in tables:
            model = table.get_model(field_ids=[])
            user_count = model.objects.count()
            user_sources_using_table = user_source_table_map[table.id]
            for user_source_using_table in user_sources_using_table:
                now = datetime.now(tz=timezone.utc)
                cache.set(
                    self._generate_update_user_count_cache_key(user_source_using_table),
                    self._generate_update_user_count_cache_value(user_count, now),
                    timeout=settings.BASEROW_ENTERPRISE_USER_SOURCE_COUNTING_CACHE_TTL_SECONDS,
                )
                if user_sources and user_source_using_table in user_sources:
                    user_source_count = UserSourceCount(
                        count=user_count,
                        last_updated=now,
                    )

        return user_source_count

    def get_user_count(
        self,
        user_source: LocalBaserowUserSource,
        force_recount: bool = False,
        update_if_uncached: bool = True,
    ) -> Optional[UserSourceCount]:
        """
        Responsible for retrieving a user source's count. If the user source isn't
        configured, `None` will be returned. If it's configured, and cached, so long
        as we're not `force_recount=True`, the cached user count will be returned.
        If the count isn't cached, or `force_recount=True`, we will count the users,
        cache the result, and return the count.

        :param user_source: The user source we want a count from.
        :param force_recount: If True, we will re-count the users and ignore any
            existing cached count.
        :param update_if_uncached: If True, we will count the users and cache the
            result if the cache entry is missing. Set this to False if you need to
            know if the cache entry is missing.
        :return: A `UserSourceCount` instance if the user source is configured,
            otherwise `None`.
        """

        # If we're being asked for the user count of a
        # misconfigured user source, we'll return None.
        if not self.is_configured(user_source):
            return None

        cached_user_source_count = self._get_cached_user_count(user_source)
        if (cached_user_source_count and not force_recount) or not update_if_uncached:
            return cached_user_source_count

        queryset = UserSourceHandler().get_user_sources(
            user_source.application,
            self.model_class.objects.filter(pk=user_source.pk),
            specific=True,
        )
        return self.update_user_count(queryset)  # type: ignore
