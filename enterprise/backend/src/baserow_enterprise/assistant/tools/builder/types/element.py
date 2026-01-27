import re
import uuid
from typing import Annotated, Literal, Optional

from pydantic import Field

from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.core.formula.types import (
    BaserowFormulaObject,
)
from baserow_enterprise.assistant.types import BaseModel

from .style import ElementStyleConfig, ElementThemeOverrides


def escape_for_formula_string(text: str) -> str:
    """
    Escape text for use in a double-quoted Baserow formula string literal.

    IMPORTANT: Baserow's formula parser does NOT interpret escape sequences like
    \\n as newlines - only quote escaping is supported. So we:
    - Escape backslashes and double quotes
    - Leave actual newlines/tabs as-is (JSON encoding handles them when stored)

    Args:
        text: Plain text to escape

    Returns:
        Escaped text wrapped in double quotes, ready for use in a formula
    """
    if not text:
        return '""'
    escaped = text.replace("\\", "\\\\")  # Backslashes first
    escaped = escaped.replace('"', '\\"')  # Double quotes
    # DO NOT escape newlines/tabs - Baserow formulas don't interpret \n \t etc.
    # Actual newlines are preserved; JSON encoding handles them when stored
    return f'"{escaped}"'


def _validate_js_syntax(js_code: str) -> None:
    """
    Validate JavaScript syntax using esprima parser.

    Args:
        js_code: JavaScript code to validate (without script tags).

    Raises:
        ValueError: If JavaScript has syntax errors.
    """
    try:
        import esprima
    except ImportError:
        # esprima not available, skip JS validation
        return

    try:
        esprima.parseScript(js_code, tolerant=True)
    except esprima.Error as e:
        raise ValueError(f"JavaScript syntax error: {e}")


def _validate_script_tag(script: str) -> str:
    """
    Validate a script tag entry. Each entry MUST be a complete <script> tag.

    Accepts:
    - External scripts: <script src="..."></script>
    - Inline scripts: <script>...</script>

    Returns:
        The validated script tag string.

    Raises:
        ValueError: If not a valid complete script tag or JS has syntax errors.
    """
    script = script.strip()
    if not script:
        return ""

    # Must start with <script
    if not script.startswith("<script"):
        raise ValueError(
            f"Each embed_js entry must be a complete <script> tag. "
            f"Got plain code instead: '{script[:60]}{'...' if len(script) > 60 else ''}'. "
            f"Wrap your code in <script>...</script> tags."
        )

    # Must end with </script>
    if not script.endswith("</script>"):
        raise ValueError(
            f"Malformed script tag: starts with <script but doesn't end with </script>. "
            f"Got: {script[:50]}...{script[-20:] if len(script) > 70 else ''}"
        )

    # Validate basic structure: <script...>...</script>
    # Match opening tag: <script> or <script src="..."> or <script type="...">
    opening_match = re.match(r"<script(\s+[^>]*)?>", script)
    if not opening_match:
        raise ValueError(f"Malformed script opening tag: {script[:50]}...")

    # Check if it's an external script (has src attribute) - no JS to validate
    if re.match(r"<script\s+[^>]*src\s*=", script):
        return script

    # Extract and validate inline JavaScript
    closing_tag_pos = script.rfind("</script>")
    opening_tag_end = opening_match.end()
    js_code = script[opening_tag_end:closing_tag_pos].strip()

    if js_code:
        _validate_js_syntax(js_code)

    return script


def build_iframe_embed_formula(
    css: Optional[str] = None,
    html: Optional[str] = None,
    js: Optional[list[str]] = None,
    data_source_mapping: Optional[dict[str, str]] = None,
) -> str:
    """
    Build a Baserow formula for iframe embed content from separate CSS, HTML, JS parts.

    Returns a formula (simple string or concat()) that evaluates to:
    <style>css</style>
    html
    <script src="..."></script>
    <script>...</script>

    Args:
        css: Plain CSS rules (no <style> tags)
        html: Plain HTML elements
        js: List of script tags. Each entry can be:
            - External script: '<script src="https://example.com/lib.js"></script>'
            - Inline script: '<script>console.log("hello");</script>'
            - Plain JS code (will be auto-wrapped in <script> tags)
        data_source_mapping: Dict mapping JS variable names to data source formulas.
            Example: {'userName': "get('data_source.5.Name')"}
            These are injected into a separate <script> block before the js scripts.

    Returns:
        A Baserow formula string that evaluates to complete HTML
    """
    parts = []

    # Add CSS section
    if css and css.strip():
        parts.append(escape_for_formula_string(f"<style>\n{css.strip()}\n</style>\n"))

    # Add HTML section
    if html and html.strip():
        parts.append(escape_for_formula_string(f"{html.strip()}\n"))

    # Add data source injection script if needed
    if data_source_mapping:
        script_parts = ["<script>\n"]
        for var_name, ds_formula in data_source_mapping.items():
            # Build: const varName = "value"; where value comes from get()
            script_parts.append(f'const {var_name} = "')
            parts.append(escape_for_formula_string("".join(script_parts)))
            parts.append(ds_formula)  # Raw formula like get('data_source.5.Name')
            script_parts = ['";\n']
        script_parts.append("</script>\n")
        parts.append(escape_for_formula_string("".join(script_parts)))

    # Add JavaScript scripts
    if js:
        for script in js:
            validated = _validate_script_tag(script)
            if validated:
                parts.append(escape_for_formula_string(f"{validated}\n"))

    if not parts:
        return '""'

    if len(parts) == 1:
        return parts[0]

    return f"concat({', '.join(parts)})"


def convert_html_to_embed_formula(html_code: str) -> str:
    """
    DEPRECATED: Use build_iframe_embed_formula() with separate css/html/js fields instead.

    Convert HTML/CSS/JS code to Baserow concat formula format.
    Kept for backwards compatibility with the legacy 'embed' field.

    Input: Normal HTML/CSS/JS (multiline string)
    Output: A properly escaped formula string
    """
    if not html_code or not html_code.strip():
        return '""'

    # Use the new escaping function which handles backslashes correctly
    return escape_for_formula_string(html_code)


class ElementBase(BaseModel):
    """Base properties for all elements."""

    parent_element_id: Optional[int] = Field(
        default=None,
        description="ID of existing parent container element (use this for adding to existing containers)",
    )
    parent_element_ref: Optional[str] = Field(
        default=None,
        description="Reference to parent container element created in the same batch",
    )
    place_in_container: Optional[str] = Field(
        default=None,
        description="Position within parent container (e.g., '0', '1' for columns)",
    )
    visibility: Literal["all", "logged-in", "not-logged"] = Field(default="all")

    # Style configuration (optional)
    style: Optional[ElementStyleConfig] = Field(
        default=None,
        description="Element-specific style (border, padding, margin, background)",
    )
    styles: Optional[ElementThemeOverrides] = Field(
        default=None,
        description="Theme property overrides for this element",
    )
    css_classes: Optional[str] = Field(
        default=None,
        description="Space-separated CSS class names",
    )

    def get_style_kwargs(self) -> dict:
        """Get style-related kwargs for element creation."""
        kwargs = {}

        # Add style properties with style_ prefix
        if self.style:
            kwargs.update(self.style.to_orm_kwargs())

        # Add theme overrides
        if self.styles is not None:
            kwargs["styles"] = self.styles.model_dump(exclude_none=True)

        # Add CSS classes
        if self.css_classes is not None:
            kwargs["css_classes"] = self.css_classes

        return kwargs


class RefCreate(BaseModel):
    """Reference for element creation, used for linking elements."""

    ref: str = Field(
        ..., description="Unique reference for this element (used in linking)"
    )


# =============================================================================
# Layout Elements
# =============================================================================


class ColumnElementCreate(ElementBase, RefCreate):
    """Multi-column layout container."""

    type: Literal["column"] = "column"
    column_amount: int = Field(default=2, ge=1, le=6, description="Number of columns")
    column_gap: int = Field(default=20, description="Gap between columns in pixels")
    alignment: Literal["top", "center", "bottom"] = Field(
        default="top", description="Vertical alignment of column content"
    )

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "column_amount": self.column_amount,
            "column_gap": self.column_gap,
            "alignment": self.alignment,
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs


class FormContainerElementCreate(ElementBase, RefCreate):
    """Form container that wraps form input elements."""

    type: Literal["form_container"] = "form_container"
    submit_button_label: str = Field(default="Submit")
    reset_initial_values_post_submission: bool = Field(default=False)

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "submit_button_label": BaserowFormulaObject.create(
                f"'{self.submit_button_label}'"
            ),
            "reset_initial_values_post_submission": self.reset_initial_values_post_submission,
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs


class SimpleContainerElementCreate(ElementBase, RefCreate):
    """Simple container for grouping elements."""

    type: Literal["simple_container"] = "simple_container"

    def to_orm_kwargs(self, user, page) -> dict:
        return self.get_style_kwargs()


# =============================================================================
# Display Elements
# =============================================================================


class HeadingElementCreate(ElementBase, RefCreate):
    """Heading text element."""

    type: Literal["heading"] = "heading"
    value: str = Field(
        ..., description="Heading text formula. Wrap simple strings in quotes."
    )
    level: Literal[1, 2, 3, 4, 5] = Field(
        default=1, description="Heading level (h1-h5)"
    )

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "value": BaserowFormulaObject.create(self.value),
            "level": self.level,
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs


class TextElementCreate(ElementBase, RefCreate):
    """Text/paragraph element."""

    type: Literal["text"] = "text"
    value: str = Field(..., description="Text formula. Wrap simple strings in quotes.")
    format: Literal["plain", "markdown"] = Field(default="plain")

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "value": BaserowFormulaObject.create(self.value),
            "format": self.format,
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs


class ButtonElementCreate(ElementBase, RefCreate):
    """Button element that triggers workflow actions."""

    type: Literal["button"] = "button"
    value: str = Field(
        ..., description="Button label formula. Wrap simple strings in quotes."
    )

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "value": BaserowFormulaObject.create(self.value),
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs


class LinkElementCreate(ElementBase, RefCreate):
    """Link or button-styled link element."""

    type: Literal["link"] = "link"
    value: str = Field(
        ..., description="Link text formula. Wrap simple strings in quotes."
    )
    variant: Literal["link", "button"] = Field(default="link")
    navigation_type: Literal["page", "custom"] = Field(default="page")
    navigate_to_page_id: Optional[int] = Field(default=None)
    navigate_to_url: Optional[str] = Field(default=None)
    page_parameters: list[dict] = Field(
        default_factory=list, description="List of {name, value} for page params"
    )
    target: Literal["self", "blank"] = Field(default="self")

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "value": BaserowFormulaObject.create(self.value),
            "variant": self.variant,
            "navigation_type": self.navigation_type,
            "target": self.target,
        }
        if self.navigation_type == "page" and self.navigate_to_page_id:
            kwargs["navigate_to_page_id"] = self.navigate_to_page_id
            kwargs["page_parameters"] = [
                {"name": p["name"], "value": BaserowFormulaObject.create(p["value"])}
                for p in self.page_parameters
            ]
        elif self.navigation_type == "custom" and self.navigate_to_url:
            kwargs["navigate_to_url"] = BaserowFormulaObject.create(
                self.navigate_to_url
            )
        kwargs.update(self.get_style_kwargs())
        return kwargs


class ImageElementCreate(ElementBase, RefCreate):
    """Image display element."""

    type: Literal["image"] = "image"
    image_source_type: Literal["upload", "url"] = Field(default="url")
    image_url: str = Field(default="", description="URL or formula for image source")
    alt_text: str = Field(default="")

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "image_source_type": self.image_source_type,
            "image_url": BaserowFormulaObject.create(self.image_url)
            if self.image_url
            else BaserowFormulaObject.create("''"),
            "alt_text": BaserowFormulaObject.create(self.alt_text)
            if self.alt_text
            else BaserowFormulaObject.create("''"),
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs


class IFrameElementCreate(ElementBase, RefCreate):
    """
    IFrame element for embedding external content or custom HTML/CSS/JS.

    Use source_type='url' to embed external pages via URL.
    Use source_type='embed' to inject custom HTML, CSS, and JavaScript directly.

    For embed mode, prefer the separate embed_css, embed_html, embed_js fields
    which allow writing plain code without escaping. The system handles all
    formula conversion automatically.
    """

    type: Literal["iframe"] = "iframe"
    source_type: Literal["url", "embed"] = Field(
        default="url",
        description="'url' to embed external page, 'embed' to inject custom HTML/CSS/JS",
    )
    url: str = Field(
        default="",
        description="URL formula for the page to embed (when source_type='url')",
    )

    # New structured embed fields - LLM writes plain code, system handles escaping
    embed_css: Optional[str] = Field(
        default=None,
        description="Plain CSS rules (no <style> tags). Write normal CSS. "
        "Example: '.container { display: flex; gap: 10px; }'",
    )
    embed_html: Optional[str] = Field(
        default=None,
        description="Plain HTML elements (no <html>/<body> tags). Write normal HTML. "
        "Example: '<div class=\"box\"><h1>Title</h1></div>'",
    )
    embed_js: Optional[list[str]] = Field(
        default=None,
        description="List of complete script blocks. Each string is ONE complete <script> tag. "
        "Use for external libraries: '<script src=\"https://cdn.example.com/lib.js\"></script>' "
        "or inline code: '<script>const x = 1; console.log(x);</script>'. "
        "IMPORTANT: Put ALL your JavaScript code inside ONE <script> tag, not one line per string.",
    )
    data_source_mapping: Optional[dict[str, str]] = Field(
        default=None,
        description="Map JS variable names to data source formulas for injection. "
        "Example: {'userName': \"get('data_source.5.Name')\"}. "
        "Creates 'const userName = \"value\";' at script start.",
    )

    height: int = Field(
        default=300,
        ge=1,
        le=2000,
        description="Height of the iframe in pixels",
    )

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "source_type": self.source_type,
            "url": BaserowFormulaObject.create(self.url)
            if self.url
            else BaserowFormulaObject.create("''"),
            "height": self.height,
        }

        # Prefer new split fields if any are provided
        has_new_fields = any([self.embed_css, self.embed_html, self.embed_js])

        if has_new_fields:
            # Use the new structured approach
            embed_formula = build_iframe_embed_formula(
                css=self.embed_css,
                html=self.embed_html,
                js=self.embed_js,
                data_source_mapping=self.data_source_mapping,
            )
            kwargs["embed"] = BaserowFormulaObject.create(embed_formula)
        elif self.embed:
            # Legacy path - use existing conversion for backwards compatibility
            kwargs["embed"] = BaserowFormulaObject.create(
                convert_html_to_embed_formula(self.embed)
            )
        else:
            kwargs["embed"] = BaserowFormulaObject.create("''")

        kwargs.update(self.get_style_kwargs())
        return kwargs


# =============================================================================
# Form Input Elements
# =============================================================================


class InputTextElementCreate(ElementBase, RefCreate):
    """Text input form element."""

    type: Literal["input_text"] = "input_text"
    label: str = Field(..., description="Input label")
    placeholder: str = Field(default="")
    default_value: str = Field(default="")
    required: bool = Field(default=False)
    validation_type: Literal["any", "email", "integer"] = Field(default="any")
    is_multiline: bool = Field(default=False)
    rows: int = Field(default=3, description="Rows for multiline input")

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "label": BaserowFormulaObject.create(f"'{self.label}'"),
            "placeholder": BaserowFormulaObject.create(f"'{self.placeholder}'"),
            "default_value": BaserowFormulaObject.create(
                self.default_value if self.default_value else "''"
            ),
            "required": self.required,
            "validation_type": self.validation_type,
            "is_multiline": self.is_multiline,
            "rows": self.rows,
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs


class ChoiceOption(BaseModel):
    """Option for choice element."""

    name: str
    value: str


class ChoiceElementCreate(ElementBase, RefCreate):
    """Dropdown or radio/checkbox choice element."""

    type: Literal["choice"] = "choice"
    label: str = Field(...)
    placeholder: str = Field(default="")
    required: bool = Field(default=False)
    multiple: bool = Field(default=False)
    show_as_dropdown: bool = Field(default=True)
    options: list[ChoiceOption] = Field(
        default_factory=list, description="List of options"
    )

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "label": BaserowFormulaObject.create(f"'{self.label}'"),
            "placeholder": BaserowFormulaObject.create(f"'{self.placeholder}'"),
            "required": self.required,
            "multiple": self.multiple,
            "show_as_dropdown": self.show_as_dropdown,
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs

    def get_options(self) -> list[dict]:
        """Get options in format for ORM."""

        return [{"name": o.name, "value": o.value} for o in self.options]


class CheckboxElementCreate(ElementBase, RefCreate):
    """Checkbox form element."""

    type: Literal["checkbox"] = "checkbox"
    label: str = Field(...)
    default_value: str = Field(default="false")
    required: bool = Field(default=False)

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "label": BaserowFormulaObject.create(f"'{self.label}'"),
            "default_value": BaserowFormulaObject.create(self.default_value),
            "required": self.required,
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs


class DateTimePickerElementCreate(ElementBase, RefCreate):
    """Date/time picker form element."""

    type: Literal["datetime_picker"] = "datetime_picker"
    label: str = Field(...)
    required: bool = Field(default=False)
    include_time: bool = Field(default=False)
    date_format: Literal["EU", "US", "ISO"] = Field(default="EU")

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "label": BaserowFormulaObject.create(f"'{self.label}'"),
            "required": self.required,
            "include_time": self.include_time,
            "date_format": self.date_format,
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs


class RecordSelectorElementCreate(ElementBase, RefCreate):
    """Record selector dropdown linked to a data source."""

    type: Literal["record_selector"] = "record_selector"
    label: str = Field(...)
    data_source_id: Optional[int] = Field(
        default=None, description="Data source ID (resolved from data_source_ref)"
    )
    required: bool = Field(default=False)
    multiple: bool = Field(default=False)
    placeholder: str = Field(default="")

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "label": BaserowFormulaObject.create(f"'{self.label}'"),
            "data_source_id": self.data_source_id,
            "required": self.required,
            "multiple": self.multiple,
            "placeholder": BaserowFormulaObject.create(f"'{self.placeholder}'"),
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs


# =============================================================================
# Collection Elements
# =============================================================================


class TableFieldConfig(BaseModel):
    """Configuration for a table column."""

    name: str = Field(..., description="Column header name")
    type: Literal["text", "link", "button", "tags"] = Field(default="text")


class TableElementCreate(ElementBase, RefCreate):
    """Table element to display data from a data source."""

    type: Literal["table"] = "table"
    data_source_id: Optional[int] = Field(
        default=None, description="Data source ID (resolved from data_source_ref)"
    )
    items_per_page: int = Field(default=20)
    button_load_more_label: str = Field(default="Load more")
    fields: list[TableFieldConfig] = Field(
        default_factory=list, description="Table column configurations"
    )

    def to_orm_kwargs(self, user, page) -> dict:
        orm_kwargs = {
            "data_source_id": self.data_source_id,
            "items_per_page": self.items_per_page,
            "button_load_more_label": BaserowFormulaObject.create(
                f"'{self.button_load_more_label}'"
            ),
        }

        if self.data_source_id and not self.fields:
            data_source = next(
                iter(
                    DataSourceHandler().get_data_sources(
                        page,
                        base_queryset=DataSource.objects.filter(id=self.data_source_id),
                        with_shared=True,
                    )
                ),
                None,
            )

            if data_source and hasattr(data_source.service, "table_id"):
                service = data_source.service
                orm_kwargs["fields"] = service.get_type().get_default_collection_fields(
                    service
                )
        orm_kwargs.update(self.get_style_kwargs())
        return orm_kwargs


class RepeatElementCreate(ElementBase, RefCreate):
    """Repeater element that duplicates children for each data source item."""

    type: Literal["repeat"] = "repeat"
    data_source_id: Optional[int] = Field(
        default=None, description="Data source ID (resolved from data_source_ref)"
    )
    orientation: Literal["vertical", "horizontal"] = Field(default="vertical")
    items_per_page: int = Field(default=20)
    items_per_row: dict = Field(
        default_factory=lambda: {"desktop": 3, "tablet": 2, "smartphone": 1}
    )

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "data_source_id": self.data_source_id,
            "orientation": self.orientation,
            "items_per_page": self.items_per_page,
            "items_per_row": self.items_per_row,
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs


# =============================================================================
# Navigation Elements
# =============================================================================


class MenuItemCreate(BaseModel):
    """A menu item linking to an internal page."""

    name: str = Field(..., description="Display text for the menu item")
    page_id: int = Field(..., description="Target page ID to navigate to")


class MenuElementCreate(ElementBase, RefCreate):
    """Menu navigation element with configurable items."""

    type: Literal["menu"] = "menu"
    orientation: Literal["horizontal", "vertical"] = Field(
        default="horizontal", description="Menu layout orientation"
    )
    alignment: Literal["left", "center", "right", "justify"] = Field(
        default="left", description="Horizontal alignment of menu items"
    )
    menu_items: list[MenuItemCreate] = Field(
        default_factory=list,
        description="List of menu items with navigation configuration",
    )

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "orientation": self.orientation,
            "alignment": self.alignment,
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs

    def get_menu_items(self) -> list[dict]:
        """Convert menu items to format expected by MenuElementType.after_create()."""
        return [
            {
                "uid": str(uuid.uuid4()),
                "type": "link",
                "variant": "link",
                "name": item.name,
                "navigation_type": "page",
                "navigate_to_page_id": item.page_id,
                "target": "self",
            }
            for item in self.menu_items
        ]


class HeaderElementCreate(ElementBase, RefCreate):
    """Header container element displayed at top of pages (multi-page)."""

    type: Literal["header"] = "header"
    share_type: Literal["all", "only", "except"] = Field(
        default="all",
        description="How to share across pages: 'all', 'only' (specific pages), 'except' (all except specific)",
    )
    page_ids: list[int] = Field(
        default_factory=list,
        description="Page IDs for 'only' or 'except' share types",
    )

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "share_type": self.share_type,
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs

    def get_page_ids(self) -> list[int]:
        """Get page IDs for multi-page association."""
        return self.page_ids


class FooterElementCreate(ElementBase, RefCreate):
    """Footer container element displayed at bottom of pages (multi-page)."""

    type: Literal["footer"] = "footer"
    share_type: Literal["all", "only", "except"] = Field(
        default="all",
        description="How to share across pages: 'all', 'only' (specific pages), 'except' (all except specific)",
    )
    page_ids: list[int] = Field(
        default_factory=list,
        description="Page IDs for 'only' or 'except' share types",
    )

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "share_type": self.share_type,
        }
        kwargs.update(self.get_style_kwargs())
        return kwargs

    def get_page_ids(self) -> list[int]:
        """Get page IDs for multi-page association."""
        return self.page_ids


# =============================================================================
# Discriminated Union
# =============================================================================

AnyElementCreate = Annotated[
    ColumnElementCreate
    | FormContainerElementCreate
    | SimpleContainerElementCreate
    | HeadingElementCreate
    | TextElementCreate
    | ButtonElementCreate
    | LinkElementCreate
    | ImageElementCreate
    | IFrameElementCreate
    | InputTextElementCreate
    | ChoiceElementCreate
    | CheckboxElementCreate
    | DateTimePickerElementCreate
    | RecordSelectorElementCreate
    | TableElementCreate
    | RepeatElementCreate
    | HeaderElementCreate
    | FooterElementCreate
    | MenuElementCreate,
    Field(discriminator="type"),
]


# =============================================================================
# Element Type Registry
# =============================================================================


class ElementTypeMapping:
    """Maps element type strings to their ORM element type names."""

    _mapping = {
        "column": "column",
        "form_container": "form_container",
        "simple_container": "simple_container",
        "heading": "heading",
        "text": "text",
        "button": "button",
        "link": "link",
        "image": "image",
        "iframe": "iframe",
        "input_text": "input_text",
        "choice": "choice",
        "checkbox": "checkbox",
        "datetime_picker": "datetime_picker",
        "record_selector": "record_selector",
        "table": "table",
        "repeat": "repeat",
        "header": "header",
        "footer": "footer",
        "menu": "menu",
    }

    @classmethod
    def get_orm_type(cls, element_type: str) -> str:
        """Get the ORM element type name for a given element type."""

        return cls._mapping.get(element_type, element_type)


element_type_mapping = ElementTypeMapping()


# =============================================================================
# Element Item (for listing)
# =============================================================================


CONTAINER_ELEMENT_TYPES = {
    "column",
    "form_container",
    "simple_container",
    "repeat",
    "header",
    "footer",
}


class ElementItem(BaseModel):
    """Existing element with ID."""

    id: int
    type: str
    order: str
    parent_element_id: Optional[int] = None
    place_in_container: Optional[str] = None
    is_container: bool = Field(
        default=False,
        description="True if this element can contain child elements (use as parent_element_id)",
    )

    @classmethod
    def from_orm(cls, element) -> "ElementItem":
        """Create ElementItem from ORM Element instance."""

        element_type = element.get_type().type
        return cls(
            id=element.id,
            type=element_type,
            order=str(element.order),
            parent_element_id=element.parent_element_id,
            place_in_container=element.place_in_container,
            is_container=element_type in CONTAINER_ELEMENT_TYPES,
        )
