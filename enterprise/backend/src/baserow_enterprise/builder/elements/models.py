from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import SET_NULL

from baserow.contrib.builder.elements.models import Element, FormElement
from baserow.core.formula.field import FormulaField


class AuthFormElement(Element):
    """
    An element to authenticate against a user source.
    """

    user_source = models.ForeignKey(
        "core.UserSource",
        null=True,
        on_delete=SET_NULL,
        help_text="Display the auth form for the selected user source",
    )

    login_button_label = FormulaField(
        help_text="The label of the login button", blank=True, default="", db_default=""
    )


class FileInputElement(FormElement):
    """
    An input element of file type.
    """

    MAX_FILE_SIZE = 100

    label = FormulaField(
        default="",
        help_text="The text label for this input",
    )
    default_name = FormulaField(default="", help_text="This input's default file name.")
    default_url = FormulaField(default="", help_text="This input's default file url.")
    help_text = FormulaField(
        default="",
        help_text="The help text which should be visible on the element.",
    )
    multiple = models.BooleanField(
        default=False,
        help_text="Whether this file input allows users to choose multiple files",
    )
    max_filesize = models.PositiveIntegerField(
        default=5,
        help_text="Maximum file size a user can upload in MB.",
        validators=[
            MinValueValidator(1, message="Value cannot be less than 1."),
            MaxValueValidator(
                MAX_FILE_SIZE,
                message=(f"Value cannot be greater than {MAX_FILE_SIZE}."),
            ),
        ],
    )
    allowed_filetypes = models.JSONField(
        default=list,
        help_text="Allowed file types for this input.",
    )
    preview = models.BooleanField(
        default=False,
        help_text="Whether to show a preview of image files.",
    )
