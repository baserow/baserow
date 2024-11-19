from typing import Any, Dict, List, Optional

from django.contrib.auth.models import AbstractUser

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
from baserow.contrib.database.rows.operations import ReadDatabaseRowOperationType
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.app_auth_providers.handler import AppAuthProviderHandler
from baserow.core.formula.validator import ensure_string
from baserow.core.handler import CoreHandler
from baserow.core.user.exceptions import UserNotFound
from baserow.core.user_sources.exceptions import UserSourceImproperlyConfigured
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.registries import UserSourceType
from baserow.core.user_sources.types import UserSourceDict, UserSourceSubClass
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

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[UserSourceSubClass] = None,
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

    def after_update(self, user, user_source, values):
        if "auth_provider" not in values and "table" in values:
            # We clear all auth provider when the table changes
            for ap in AppAuthProviderHandler.list_app_auth_providers_for_user_source(
                user_source
            ):
                ap.get_type().after_user_source_update(user, ap, user_source)

        return super().after_update(user, user_source, values)

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
            return id_mapping["database_tables"][value]

        if (
            value
            and "database_fields" in id_mapping
            and prop_name in ("email_field_id", "name_field_id", "role_field_id")
        ):
            return id_mapping["database_fields"][value]

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def get_user_model(self, user_source):
        try:
            # Use table handler to exclude trashed table
            table = TableHandler().get_table(user_source.table_id)
        except TableDoesNotExist as exc:
            # As we CASCADE when a table is deleted, the table shouldn't
            # exist only if it's trashed and not yet deleted.
            raise UserSourceImproperlyConfigured("The table doesn't exist.") from exc

        integration = user_source.integration.specific

        model = table.get_model()

        CoreHandler().check_permissions(
            integration.authorized_user,
            ReadDatabaseRowOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        return model

    def is_configured(self, user_source):
        """
        Returns True if the user source is configured properly. False otherwise.
        """

        return (
            user_source.email_field_id is not None
            and user_source.name_field_id is not None
            and user_source.table_id is not None
            and user_source.integration_id is not None
        )

    def gen_uid(self, user_source):
        """
        We want to invalidate user tokens if the table or the email field change.
        """

        return (
            f"{user_source.id}"
            f"_{user_source.table_id if user_source.table_id else '?'}"
            f"_{user_source.email_field_id if user_source.email_field_id else '?'}"
            f"_{user_source.role_field_id if user_source.role_field_id else '?'}"
        )

    def role_type_is_allowed(self, role_field: Optional[FieldType]) -> bool:
        """Return True if the Role Field's type is allowed, False otherwise."""

        if role_field is None:
            return False

        return role_field.get_type().type in self.field_types_allowed_as_role

    def get_user_role(self, user, user_source: UserSource) -> str:
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

    def list_users(self, user_source: UserSource, count: int = 5, search: str = ""):
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

    def get_roles(self, user_source: UserSource) -> List[str]:
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

    def get_user(self, user_source: UserSource, **kwargs):
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
                getattr(user, user_source.name_field.db_column),
                getattr(user, user_source.email_field.db_column),
                self.get_user_role(user, user_source),
            )

        raise UserNotFound()

    def authenticate(self, user_source: UserSource, **kwargs):
        """
        Authenticates using the given credentials. It uses the password auth provider.
        """

        if not self.is_configured(user_source):
            raise UserSourceImproperlyConfigured()

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
