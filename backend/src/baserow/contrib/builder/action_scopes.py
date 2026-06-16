from typing import Optional, cast

from django.utils.translation import gettext_lazy as _

from rest_framework import serializers

from baserow.core.action.registries import ActionScopeStr, ActionScopeType

ELEMENT_ACTION_CONTEXT = _(
    'of type "%(element_type)s" on page (%(page_id)s) in builder '
    '"%(builder_name)s" (%(builder_id)s).'
)


class PageActionScopeType(ActionScopeType):
    type = "page"

    @classmethod
    def value(cls, page_id: int) -> ActionScopeStr:
        return cast(ActionScopeStr, cls.type + str(page_id))

    def get_request_serializer_field(self) -> serializers.Field:
        return serializers.IntegerField(
            min_value=0,
            allow_null=True,
            required=False,
            help_text="If set to a page id then any actions directly related "
            "to that page will be included when undoing or redoing.",
        )

    def valid_serializer_value_to_scope_str(
        self, value: int
    ) -> Optional[ActionScopeStr]:
        return self.value(value)


class SharedPageActionScopeType(ActionScopeType):
    """
    Scope for elements living on a builder's shared page (header/footer elements
    and their children). These elements appear on every content page, so their
    actions are scoped to the shared page id rather than a content page id. The
    editor sends this scope alongside the content `page` scope (they are different
    scope types, so both can be present in a single undo/redo request), which lets
    shared-element edits be undone while editing any content page.
    """

    type = "shared_page"

    @classmethod
    def value(cls, shared_page_id: int) -> ActionScopeStr:
        return cast(ActionScopeStr, cls.type + str(shared_page_id))

    def get_request_serializer_field(self) -> serializers.Field:
        return serializers.IntegerField(
            min_value=0,
            allow_null=True,
            required=False,
            help_text="If set to a shared page id then any actions related to that "
            "builder's shared elements will be included when undoing or redoing.",
        )

    def valid_serializer_value_to_scope_str(
        self, value: int
    ) -> Optional[ActionScopeStr]:
        return self.value(value)
