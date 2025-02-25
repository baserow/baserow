from typing import Any, Dict, Optional, Tuple

from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import AbstractUser

from rest_framework import exceptions, serializers

from baserow.api.exceptions import RequestBodyValidationException
from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.field_types import PasswordFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.core.app_auth_providers.auth_provider_types import AppAuthProviderType
from baserow.core.app_auth_providers.types import AppAuthProviderTypeDict
from baserow.core.auth_provider.types import AuthProviderModelSubClass
from baserow.core.user_sources.types import UserSourceSubClass
from baserow.core.user_sources.user_source_user import UserSourceUser
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowPasswordAppAuthProvider,
)
from baserow_enterprise.integrations.local_baserow.user_source_types import (
    LocalBaserowUserSourceType,
)


class LocalBaserowPasswordAppAuthProviderType(AppAuthProviderType):
    type = "local_baserow_password"
    model_class = LocalBaserowPasswordAppAuthProvider
    compatible_user_source_types = [LocalBaserowUserSourceType.type]
    field_types_allowed_as_password = [
        PasswordFieldType.type,
    ]

    serializer_field_names = ["password_field_id"]
    public_serializer_field_names = []

    allowed_fields = ["password_field"]

    serializer_field_overrides = {
        "password_field_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text="The id of the field to use as password for the user account.",
        ),
    }
    public_serializer_field_overrides = {}

    class SerializedDict(AppAuthProviderTypeDict):
        password_field_id: int

    def can_create_new_providers(
        self, user_source: Optional[UserSourceSubClass] = None, **kwargs
    ) -> bool:
        """
        Returns True if it's possible to create an authentication provider of this type.
        """

        return not LocalBaserowPasswordAppAuthProvider.objects.filter(
            user_source=user_source
        ).exists()

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[LocalBaserowPasswordAppAuthProvider] = None,
    ) -> Dict[str, Any]:
        """Load the table instance instead of the ID."""

        # We resolve the user_source first
        values = super().prepare_values(values, user)

        table_to_check = None

        if instance:
            table_to_check = instance.user_source.specific.table
        if "user_source" in values:
            table_to_check = values["user_source"].table

        # Check that the password field belongs to the user_source table
        if "password_field_id" in values:
            field_id = values.pop("password_field_id")
            if field_id is not None:
                if not table_to_check:
                    raise RequestBodyValidationException(
                        {
                            "password_field_id": [
                                {
                                    "detail": "Please select a table before selecting "
                                    "this field.",
                                    "code": "missing_table",
                                }
                            ]
                        }
                    )

                try:
                    field = FieldHandler().get_field(field_id)
                except FieldDoesNotExist as exc:
                    raise RequestBodyValidationException(
                        {
                            "password_field_id": [
                                {
                                    "detail": "The provided Id doesn't exist.",
                                    "code": "invalid_field",
                                }
                            ]
                        }
                    ) from exc

                if not table_to_check or field.table_id != table_to_check.id:
                    raise RequestBodyValidationException(
                        {
                            "password_field_id": [
                                {
                                    "detail": f"The field with ID {field_id} is "
                                    "not related to the given table.",
                                    "code": "invalid_field",
                                }
                            ]
                        }
                    )
                if field.get_type().type not in self.field_types_allowed_as_password:
                    raise RequestBodyValidationException(
                        {
                            "password_field_id": [
                                {
                                    "detail": "This field type can't be used as "
                                    "password.",
                                    "code": "invalid_field",
                                }
                            ]
                        }
                    )
                values["password_field"] = field
            else:
                values["password_field"] = None

        return values

    def after_user_source_update(
        self,
        user: "AbstractUser",
        instance: LocalBaserowPasswordAppAuthProvider,
        user_source,
    ):
        """
        Removes password field if table id has changed.
        """

        if (
            instance.password_field_id
            and instance.password_field.table_id != user_source.table_id
        ):
            instance.password_field = None
            instance.save()

    def get_or_create_user_and_sign_in(
        self, auth_provider: AuthProviderModelSubClass, user_info: Dict[str, Any]
    ) -> Tuple[AbstractUser, bool]:
        """
        Not implemented yet.
        """

    def is_configured(self, auth_provider: AuthProviderModelSubClass):
        """
        Returns True if the auth_provider is configured properly. False otherwise.
        """

        return bool(auth_provider.password_field_id)

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
        Map password field id.
        """

        if (
            prop_name == "password_field_id"
            and value
            and "database_fields" in id_mapping
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

    def get_user_model_field_ids(self, auth_provider: AuthProviderModelSubClass):
        """
        This method is specific to local_baserow app_auth_providers to return the list
        of fields used by this provider to select them on the table model to save
        queries.
        """

        return (
            [auth_provider.password_field_id] if auth_provider.password_field_id else []
        )

    def authenticate(
        self,
        auth_provider: AuthProviderModelSubClass,
        email: str,
        password: str,
    ) -> UserSourceUser:
        """
        Authenticates the user with given email using the select password field.
        """

        user_source = auth_provider.user_source.specific

        user = user_source.get_type().get_user(user_source, email=email)

        encoded_password = getattr(
            user.original_user, f"field_{auth_provider.password_field_id}"
        )

        if encoded_password and check_password(password, encoded_password):
            return user
        else:
            raise exceptions.AuthenticationFailed(
                "Your credentials are invalid.",
                "invalid_credentials",
            )
