from typing import Any

from rest_framework import serializers

from baserow.core.registry import Instance, Registry


class UserPreferenceType(Instance):
    """
    A per user, cross device setting such as the sort order of a listing page. The
    values live in a single JSON dict on the user profile; registering a type here
    is what makes a key valid, gives it a default and validates the values that
    can be stored for it.
    """

    default: Any = None

    def get_serializer_field(self) -> serializers.Field:
        """
        :return: The field that validates a value submitted for this preference.
        """

        raise NotImplementedError


class ChoiceUserPreferenceType(UserPreferenceType):
    """
    A preference that accepts one value out of a fixed list.
    """

    choices: list[str] = []

    def get_serializer_field(self) -> serializers.Field:
        return serializers.ChoiceField(choices=self.choices)


class UserPreferenceTypeRegistry(Registry[UserPreferenceType]):
    name = "user_preference"

    def get_defaults(self) -> dict[str, Any]:
        """
        :return: The default value of every registered preference, keyed by type.
        """

        return {
            preference_type.type: preference_type.default
            for preference_type in self.get_all()
        }


user_preference_type_registry: UserPreferenceTypeRegistry = UserPreferenceTypeRegistry()
