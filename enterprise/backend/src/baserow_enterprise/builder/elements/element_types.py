import mimetypes
from typing import Any, Dict, List, Optional

from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers

from baserow.api.exceptions import RequestBodyValidationException
from baserow.contrib.builder.constants import COLOR_FIELD_MAX_LENGTH, TextFormats
from baserow.contrib.builder.elements.element_types import InputElementType
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.registries import ElementType
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.types import ElementDict
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_SIMPLE,
    BaserowFormula,
    BaserowFormulaObject,
)
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.user_sources.handler import UserSourceHandler
from baserow_enterprise.builder.elements.models import (
    AuthFormElement,
    FileInputElement,
    GraphElement,
)
from baserow_enterprise.features import BUILDER_FILE_INPUT, BUILDER_GRAPH_ELEMENT
from baserow_premium.dashboard.widgets.models import ChartSeriesChartType
from baserow_premium.license.handler import LicenseHandler


class GraphElementSeriesSerializer(serializers.Serializer):
    label = FormulaSerializerField(required=False)
    values = FormulaSerializerField(required=False)
    color = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=COLOR_FIELD_MAX_LENGTH
    )
    chart_type = serializers.ChoiceField(
        choices=ChartSeriesChartType.choices,
        required=False,
        default=ChartSeriesChartType.BAR,
    )


class AuthFormElementType(ElementType):
    """
    Element that use the selected user source to generate the login form/buttons.
    """

    display_name = _("Auth form")
    type = "auth_form"
    model_class = AuthFormElement
    allowed_fields = ["user_source", "user_source_id", "login_button_label"]
    serializer_field_names = ["user_source_id", "login_button_label"]
    simple_formula_fields = ["login_button_label"]

    class SerializedDict(ElementDict):
        user_source_id: int
        login_button_label: BaserowFormula

    def get_event_names(self, instance: AuthFormElement) -> List[str]:
        return [EventTypes.AFTER_LOGIN.value]

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            ButtonThemeConfigBlockType,
            InputThemeConfigBlockType,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = {
            "user_source_id": serializers.IntegerField(
                allow_null=True,
                default=None,
                help_text=AuthFormElement._meta.get_field("user_source").help_text,
                required=False,
            ),
            "login_button_label": FormulaSerializerField(
                help_text=AuthFormElement._meta.get_field(
                    "login_button_label"
                ).help_text,
                required=False,
            ),
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_names=["login_button", "input"],
                theme_config_block_type_names=[
                    [ButtonThemeConfigBlockType.type],
                    [InputThemeConfigBlockType.type],
                ],
                serializer_kwargs={"required": False},
            ),
        }

        return overrides

    def prepare_value_for_db(
        self, values: Dict, instance: Optional[AuthFormElement] = None
    ):
        if "user_source_id" in values:
            user_source_id = values.pop("user_source_id")
            if user_source_id is not None:
                user_source = UserSourceHandler().get_user_source(user_source_id)
                if instance:
                    current_page = PageHandler().get_page(instance.page_id)
                else:
                    current_page = values["page"]

                if current_page.builder_id != user_source.application_id:
                    raise RequestBodyValidationException(
                        {
                            "user_source_id": [
                                {
                                    "detail": "The provided user source doesn't belong "
                                    "to the same application.",
                                    "code": "invalid_user_source",
                                }
                            ]
                        }
                    )
                values["user_source"] = user_source
            else:
                values["user_source"] = None

        return super().prepare_value_for_db(values, instance)

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> Any:
        if prop_name == "user_source_id" and value:
            return id_mapping["user_sources"][value]

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def get_pytest_params(self, pytest_data_fixture):
        return {
            "user_source_id": None,
        }


class FileInputElementType(InputElementType):
    display_name = _("File input")
    type = "input_file"
    model_class = FileInputElement
    allowed_fields = [
        "label",
        "label_format",
        "multiple",
        "required",
        "default_name",
        "default_url",
        "help_text",
        "help_text_format",
        "max_filesize",
        "allowed_filetypes",
        "preview",
    ]
    serializer_field_names = [
        "label",
        "label_format",
        "multiple",
        "required",
        "default_name",
        "default_url",
        "help_text",
        "help_text_format",
        "max_filesize",
        "allowed_filetypes",
        "preview",
    ]
    simple_formula_fields = [
        "label",
        "default_name",
        "default_url",
        "help_text",
    ]

    class SerializedDict(ElementDict):
        label: BaserowFormula
        label_format: str
        required: bool
        multiple: bool
        default_name: BaserowFormula
        default_url: BaserowFormula
        help_text: BaserowFormula
        help_text_format: str
        max_filesize: int
        allowed_filetypes: list
        preview: bool

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            InputThemeConfigBlockType,
            TypographyThemeConfigBlockType,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = {
            "label": FormulaSerializerField(
                help_text=FileInputElement._meta.get_field("label").help_text,
                required=False,
            ),
            "default_name": FormulaSerializerField(
                help_text=FileInputElement._meta.get_field("default_name").help_text,
                required=False,
            ),
            "default_url": FormulaSerializerField(
                help_text=FileInputElement._meta.get_field("default_url").help_text,
                required=False,
            ),
            "help_text": FormulaSerializerField(
                help_text=FileInputElement._meta.get_field("help_text").help_text,
                required=False,
            ),
            "label_format": serializers.ChoiceField(
                choices=TextFormats.choices,
                default=TextFormats.PLAIN,
                required=False,
                help_text=FileInputElement._meta.get_field("label_format").help_text,
            ),
            "help_text_format": serializers.ChoiceField(
                choices=TextFormats.choices,
                default=TextFormats.PLAIN,
                required=False,
                help_text=FileInputElement._meta.get_field(
                    "help_text_format"
                ).help_text,
            ),
            "max_filesize": serializers.IntegerField(
                help_text=FileInputElement._meta.get_field("preview").help_text,
                min_value=1,
                max_value=FileInputElement.MAX_FILE_SIZE,
                default=5,
            ),
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_names=["input"],
                theme_config_block_type_names=[
                    [
                        InputThemeConfigBlockType.type,
                        TypographyThemeConfigBlockType.type,
                    ]
                ],
                serializer_kwargs={"required": False},
            ),
        }

        return overrides

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(BUILDER_FILE_INPUT, workspace)

    def get_pytest_params(self, pytest_data_fixture):
        return {
            "label": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "required": False,
            "multiple": False,
            "default_name": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "default_url": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "help_text": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "max_filesize": 5,
            "allowed_filetypes": [],
            "preview": False,
        }

    def is_allowed_content_type(
        self, element: FileInputElement, content_type: str
    ) -> bool:
        allowed_filetypes = element.allowed_filetypes

        if not allowed_filetypes:
            return True

        extensions = mimetypes.guess_all_extensions(content_type)

        for allowed_type in allowed_filetypes:
            # special cases for media
            if allowed_type == "image/*" and content_type.startswith("image/"):
                return True
            if allowed_type == "video/*" and content_type.startswith("video/"):
                return True
            if allowed_type == "audio/*" and content_type.startswith("audio/"):
                return True
            # Users are not expected to add the dot...
            if f".{allowed_type}" in extensions:
                return True
            # but if they do...
            if allowed_type in extensions:
                return True

        return False

    def _handle_file(
        self,
        element: FileInputElement,
        file_obj: dict,
        dispatch_context: DispatchContext,
    ):
        if (
            isinstance(file_obj, dict)
            and file_obj.get("__file__")
            and not file_obj.get("url")
        ):
            file_content = dispatch_context.request.FILES.get(file_obj["file"])

            if not self.is_allowed_content_type(element, file_content.content_type):
                raise TypeError(
                    f"The file {file_obj.get('name') or 'unnamed'} type is not allowed."
                )

            if file_content.size / 1024 / 1024 > element.max_filesize:
                raise ValueError(
                    f"The file {file_obj.get('name') or 'unnamed'} "
                    f"is too large. Max {element.max_filesize}MB"
                )

            return {
                **file_obj,
                "file": file_content,
                "content_type": file_content.content_type,
            }
        else:
            return file_obj

    def is_valid(
        self, element: FileInputElement, value: Any, dispatch_context: DispatchContext
    ) -> bool:
        """
        :param element: The element we're trying to use form data in.
        :param value: The form data value, which may be invalid.
        :return: The validated value or raise if invalid.
        """

        if value is not None:
            if element.multiple:
                return [self._handle_file(element, v, dispatch_context) for v in value]
            else:
                return self._handle_file(element, value, dispatch_context)

        return value


class GraphElementType(ElementType):
    type = "graph"
    model_class = GraphElement
    allowed_fields = ["labels", "series"]
    serializer_field_names = ["labels", "series"]
    simple_formula_fields = ["labels"]

    class SerializedDict(ElementDict):
        labels: BaserowFormula
        series: list[dict[str, BaserowFormula | str]]

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.builder.api.theme.serializers import (
            DynamicConfigBlockSerializer,
        )
        from baserow.contrib.builder.theme.theme_config_block_types import (
            TypographyThemeConfigBlockType,
        )

        return {
            "labels": FormulaSerializerField(
                help_text=GraphElement._meta.get_field("labels").help_text,
                required=False,
            ),
            "series": serializers.ListSerializer(
                child=GraphElementSeriesSerializer(),
                required=False,
                help_text=GraphElement._meta.get_field("series").help_text,
            ),
            "styles": DynamicConfigBlockSerializer(
                required=False,
                property_names=["graph"],
                theme_config_block_type_names=[
                    [TypographyThemeConfigBlockType.type],
                ],
                serializer_kwargs={"required": False},
            ),
        }

    def enhance_queryset(self, queryset: QuerySet[Element]) -> QuerySet[Element]:
        return super().enhance_queryset(queryset)

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(
            BUILDER_GRAPH_ELEMENT, workspace
        )

    def formula_generator(self, element: Element):
        yield from super().formula_generator(element)

        for series in element.series:
            for formula_field in ["label", "values"]:
                new_formula = yield BaserowFormulaObject.to_formula(
                    series.get(formula_field, "")
                )
                if new_formula is not None:
                    series[formula_field] = new_formula
                    yield element

    def get_pytest_params(self, pytest_data_fixture):
        return {
            "labels": BaserowFormulaObject(
                formula="to_array('A,B')",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "series": [
                {
                    "label": BaserowFormulaObject(
                        formula="'Count'",
                        mode=BASEROW_FORMULA_MODE_SIMPLE,
                        version=BASEROW_FORMULA_VERSION_INITIAL,
                    ),
                    "values": BaserowFormulaObject(
                        formula="to_array('1,2')",
                        mode=BASEROW_FORMULA_MODE_SIMPLE,
                        version=BASEROW_FORMULA_VERSION_INITIAL,
                    ),
                    "color": "#2e90fa",
                    "chart_type": ChartSeriesChartType.BAR,
                }
            ],
        }
