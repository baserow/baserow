from baserow.contrib.database.fields.dependencies.models import FieldDependency
from baserow.core.models import Application

from .field_rules.models import FieldRule
from .fields.models import (
    BooleanField,
    DateField,
    EmailField,
    Field,
    LinkRowField,
    LongTextField,
    NumberField,
    PhoneNumberField,
    RatingField,
    TextField,
    URLField,
)
from .table.models import Table
from .tokens.models import Token, TokenPermission
from .views.models import (
    FormView,
    FormViewFieldOptions,
    GalleryView,
    GalleryViewFieldOptions,
    GridView,
    GridViewFieldOptions,
    View,
    ViewFilter,
)
from .webhooks.models import (
    TableWebhook,
    TableWebhookCall,
    TableWebhookEvent,
    TableWebhookHeader,
)

__all__ = [
    "Database",
    "Table",
    "View",
    "GridView",
    "GridViewFieldOptions",
    "GalleryView",
    "GalleryViewFieldOptions",
    "FormView",
    "FormViewFieldOptions",
    "ViewFilter",
    "Field",
    "TextField",
    "NumberField",
    "RatingField",
    "LongTextField",
    "BooleanField",
    "DateField",
    "LinkRowField",
    "URLField",
    "EmailField",
    "PhoneNumberField",
    "Token",
    "TokenPermission",
    "TableWebhook",
    "TableWebhookEvent",
    "TableWebhookHeader",
    "TableWebhookCall",
    "FieldDependency",
    "FieldRule",
]


class Database(Application):
    def get_parent(self):
        # This is a bit of a hack to prevent an unecesary query to the database to
        # get the parent workspace that we already have.
        if "workspace" in self._state.fields_cache:
            self.application_ptr.workspace = self.workspace
        return self.application_ptr
