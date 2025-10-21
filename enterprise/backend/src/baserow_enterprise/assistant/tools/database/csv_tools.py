import csv
import io
from collections import Counter
from datetime import datetime
from typing import Any, Callable, TYPE_CHECKING

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext as _

from baserow.core.models import Workspace
from baserow.core.user_files.models import UserFile
from baserow_enterprise.assistant.tools.registries import AssistantToolType

from . import utils

if TYPE_CHECKING:
    from baserow_enterprise.assistant.assistant import ToolHelpers


def detect_field_type(values: list[str]) -> tuple[str, dict[str, Any]]:
    """
    Analyzes sample values to detect the most appropriate Baserow field type.

    Returns:
        tuple: (field_type, metadata) where metadata contains type-specific info
    """
    # Filter out empty/None values for analysis
    non_empty_values = [v for v in values if v and v.strip()]

    if not non_empty_values:
        return ("text", {})

    # Try boolean detection first (most specific)
    boolean_values = {"true", "false", "yes", "no", "1", "0", "t", "f", "y", "n"}
    if all(v.lower() in boolean_values for v in non_empty_values):
        return ("boolean", {})

    # Try number detection
    try:
        numeric_values = [float(v.replace(",", "")) for v in non_empty_values]
        # Check if all are integers
        if all(v.is_integer() for v in numeric_values):
            return ("number", {"number_decimal_places": 0})
        else:
            # Find max decimal places
            max_decimals = max(
                len(str(v).split(".")[-1]) if "." in str(v) else 0
                for v in numeric_values
            )
            return ("number", {"number_decimal_places": min(max_decimals, 10)})
    except (ValueError, AttributeError):
        pass

    # Try date/datetime detection
    date_formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%m/%d/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    ]

    for date_format in date_formats:
        try:
            parsed_dates = [datetime.strptime(v, date_format) for v in non_empty_values]
            # If at least 80% parse successfully, consider it a date
            if len(parsed_dates) >= len(non_empty_values) * 0.8:
                has_time = "%H" in date_format
                return (
                    "date",
                    {
                        "date_include_time": has_time,
                        "date_format": "ISO" if "Y-m-d" in date_format else "US",
                    },
                )
        except (ValueError, TypeError):
            continue

    # Check for single_select candidate (low cardinality)
    unique_values = set(non_empty_values)
    cardinality_ratio = len(unique_values) / len(non_empty_values)

    if len(unique_values) <= 20 and cardinality_ratio < 0.3:
        return (
            "single_select",
            {"select_options": sorted(list(unique_values))[:20]},  # Limit to 20 options
        )

    # Check if it's long text (average length > 200 characters)
    avg_length = sum(len(v) for v in non_empty_values) / len(non_empty_values)
    if avg_length > 200:
        return ("long_text", {})

    # Default to text
    return ("text", {})


def get_analyze_csv_file_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[int, int], dict[str, Any]]:
    """
    Returns a function that analyzes a CSV file structure and content.
    """

    def analyze_csv_file(file_id: int, preview_rows: int = 10) -> dict[str, Any]:
        """
        Analyzes the structure and content of a CSV file.

        Args:
            file_id: The ID of the UserFile containing the CSV
            preview_rows: Number of rows to include in preview (default: 10)

        Returns:
            Dictionary containing:
            - columns: List of column info with names, detected types, and metadata
            - preview_data: Sample rows from the CSV
            - total_rows: Estimated total number of rows
            - encoding: Detected file encoding
            - delimiter: Detected CSV delimiter
        """
        nonlocal user, tool_helpers

        tool_helpers.update_status(_("Analyzing CSV file..."))

        try:
            # Get the UserFile
            user_file = UserFile.objects.get(id=file_id, uploaded_by=user)

            # Read the file content
            with user_file.open() as f:
                # Read a sample to detect encoding and delimiter
                sample = f.read(10000)
                f.seek(0)

                # Try to decode with common encodings
                encoding = "utf-8"
                try:
                    sample_str = sample.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        sample_str = sample.decode("latin-1")
                        encoding = "latin-1"
                    except UnicodeDecodeError:
                        sample_str = sample.decode("cp1252", errors="ignore")
                        encoding = "cp1252"

                # Detect delimiter
                sniffer = csv.Sniffer()
                try:
                    delimiter = sniffer.sniff(sample_str[:1000]).delimiter
                except csv.Error:
                    delimiter = ","  # Default to comma

                # Reset file pointer and read the entire content
                f.seek(0)
                content = f.read().decode(encoding)

                # Parse CSV
                csv_reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)

                # Read all rows (we need them for type detection)
                all_rows = list(csv_reader)
                total_rows = len(all_rows)

                if total_rows == 0:
                    return {
                        "error": "CSV file is empty",
                        "columns": [],
                        "preview_data": [],
                        "total_rows": 0,
                    }

                # Get column names
                fieldnames = csv_reader.fieldnames or list(all_rows[0].keys())

                # Analyze each column
                columns = []
                for col_name in fieldnames:
                    # Collect sample values (up to 100 for type detection)
                    sample_values = [row.get(col_name, "") for row in all_rows[:100]]

                    # Detect field type
                    detected_type, metadata = detect_field_type(sample_values)

                    # Calculate statistics
                    non_empty = [v for v in sample_values if v and v.strip()]
                    null_count = len(sample_values) - len(non_empty)
                    unique_count = len(set(non_empty))

                    columns.append(
                        {
                            "name": col_name,
                            "detected_type": detected_type,
                            "metadata": metadata,
                            "null_percentage": (null_count / len(sample_values) * 100)
                            if sample_values
                            else 0,
                            "unique_values": unique_count,
                            "sample_values": non_empty[:5],  # First 5 non-empty values
                        }
                    )

                # Prepare preview data
                preview_data = all_rows[:preview_rows]

                return {
                    "columns": columns,
                    "preview_data": preview_data,
                    "total_rows": total_rows,
                    "encoding": encoding,
                    "delimiter": delimiter,
                    "file_name": user_file.original_name,
                }

        except UserFile.DoesNotExist:
            return {"error": f"File with ID {file_id} not found or access denied"}
        except csv.Error as e:
            return {"error": f"CSV parsing error: {str(e)}"}
        except Exception as e:
            return {"error": f"Error analyzing CSV: {str(e)}"}

    return analyze_csv_file


class AnalyzeCsvFileToolType(AssistantToolType):
    type = "analyze_csv_file"
    thinking_message = "Analyzing CSV file..."

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_analyze_csv_file_tool(user, workspace, tool_helpers)


def get_match_csv_to_table_schema_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[int, int], dict[str, Any]]:
    """
    Returns a function that matches CSV structure against a table schema.
    """

    def match_csv_to_table_schema(file_id: int, table_id: int) -> dict[str, Any]:
        """
        Compares CSV structure with table schema and suggests actions.

        Args:
            file_id: The ID of the UserFile containing the CSV
            table_id: The ID of the table to match against

        Returns:
            Dictionary containing match analysis and suggestions
        """
        nonlocal user, workspace, tool_helpers

        tool_helpers.update_status(_("Matching CSV to table schema..."))

        # Get CSV analysis
        analyze_tool = get_analyze_csv_file_tool(user, workspace, tool_helpers)
        csv_analysis = analyze_tool(file_id, preview_rows=5)

        if "error" in csv_analysis:
            return csv_analysis

        # Get table schema
        table = utils.filter_tables(user, workspace).get(id=table_id)
        table_schema = utils.get_tables_schema([table], full_schema=True)[0]

        # Build field name mapping (case-insensitive, strip whitespace)
        table_fields = {
            field.name.lower().strip(): field
            for field in [table_schema.primary_field] + table_schema.fields
        }

        # Analyze matches
        matched_fields = []
        missing_fields = []  # CSV columns not in table
        type_mismatches = []

        for csv_col in csv_analysis["columns"]:
            csv_name = csv_col["name"].lower().strip()
            csv_type = csv_col["detected_type"]

            if csv_name in table_fields:
                table_field = table_fields[csv_name]
                # Check type compatibility
                if is_type_compatible(csv_type, table_field.type):
                    matched_fields.append(
                        {
                            "csv_column": csv_col["name"],
                            "table_field": table_field.name,
                            "compatible": True,
                        }
                    )
                else:
                    matched_fields.append(
                        {
                            "csv_column": csv_col["name"],
                            "table_field": table_field.name,
                            "compatible": False,
                        }
                    )
                    type_mismatches.append(
                        {
                            "field_name": csv_col["name"],
                            "csv_type": csv_type,
                            "table_type": table_field.type,
                            "suggestion": f"CSV has {csv_type}, table has {table_field.type}",
                        }
                    )
            else:
                # CSV column not in table
                missing_fields.append(
                    {
                        "name": csv_col["name"],
                        "detected_type": csv_type,
                        "metadata": csv_col["metadata"],
                    }
                )

        # Find extra fields (table fields not in CSV)
        csv_col_names = {col["name"].lower().strip() for col in csv_analysis["columns"]}
        extra_fields = [
            field.name
            for field_name, field in table_fields.items()
            if field_name not in csv_col_names and not field.primary
        ]

        # Calculate match score
        total_csv_cols = len(csv_analysis["columns"])
        matched_count = len([m for m in matched_fields if m["compatible"]])
        match_score = matched_count / total_csv_cols if total_csv_cols > 0 else 0

        # Generate suggestions
        suggestions = []

        if match_score == 1.0:
            suggestions.append("Perfect match! Ready to import.")
        elif match_score >= 0.7:
            if missing_fields:
                suggestions.append(
                    f"Create {len(missing_fields)} new field(s): "
                    + ", ".join(f["name"] for f in missing_fields)
                )
            if type_mismatches:
                suggestions.append(
                    "Some type mismatches detected. Data will be adapted during import."
                )
        elif match_score >= 0.4:
            suggestions.append(
                "Moderate match. Consider creating missing fields or creating a new table."
            )
            if missing_fields:
                suggestions.append(
                    f"Missing fields: {', '.join(f['name'] for f in missing_fields)}"
                )
        else:
            suggestions.append(
                "Low match score. Recommend creating a new table for this CSV."
            )

        return {
            "match_score": match_score,
            "total_csv_columns": total_csv_cols,
            "matched_fields": matched_count,
            "perfect_match": match_score == 1.0,
            "missing_fields": missing_fields,
            "extra_table_fields": extra_fields,
            "type_mismatches": type_mismatches,
            "suggestions": suggestions,
            "csv_info": {
                "file_name": csv_analysis["file_name"],
                "total_rows": csv_analysis["total_rows"],
            },
        }

    return match_csv_to_table_schema


def is_type_compatible(csv_type: str, table_type: str) -> bool:
    """
    Checks if a CSV column type is compatible with a table field type.
    """
    # Define compatibility matrix
    compatibility = {
        "text": ["text", "long_text", "url", "email", "phone_number"],
        "long_text": ["text", "long_text"],
        "number": ["number", "rating", "count"],
        "boolean": ["boolean"],
        "date": ["date", "last_modified", "created_on"],
        "single_select": ["single_select", "text", "long_text"],
    }

    compatible_types = compatibility.get(csv_type, [])
    return table_type in compatible_types


class MatchCsvToTableSchemaToolType(AssistantToolType):
    type = "match_csv_to_table_schema"
    thinking_message = "Checking CSV compatibility with table..."

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_match_csv_to_table_schema_tool(user, workspace, tool_helpers)


def get_import_csv_rows_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[int, int, int, int], dict[str, Any]]:
    """
    Returns a function that imports CSV rows into a table with batch processing.
    """

    def import_csv_rows(
        file_id: int,
        table_id: int,
        start_row: int = 0,
        batch_size: int = 20,
    ) -> dict[str, Any]:
        """
        Imports a batch of rows from a CSV file into a table.

        Args:
            file_id: The ID of the UserFile containing the CSV
            table_id: The ID of the table to import into
            start_row: Starting row index (0-based, default: 0)
            batch_size: Number of rows to import (default: 20, max: 20)

        Returns:
            Dictionary with import results and pagination info
        """
        nonlocal user, workspace, tool_helpers

        # Limit batch size to 20 (create_rows constraint)
        batch_size = min(batch_size, 20)

        tool_helpers.update_status(
            _("Importing rows %(start)s-%(end)s...")
            % {"start": start_row + 1, "end": start_row + batch_size}
        )

        try:
            # Get the table and UserFile
            table = utils.filter_tables(user, workspace).get(id=table_id)
            user_file = UserFile.objects.get(id=file_id, uploaded_by=user)

            # Get table schema and create_rows tool
            table_tools = utils.get_table_rows_tools(
                user, workspace, tool_helpers, table
            )
            create_rows_tool = table_tools["create"]

            # Read CSV file
            with user_file.open() as f:
                # Detect encoding
                sample = f.read(10000)
                f.seek(0)

                encoding = "utf-8"
                try:
                    sample.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        sample.decode("latin-1")
                        encoding = "latin-1"
                    except UnicodeDecodeError:
                        encoding = "cp1252"

                # Read full content
                f.seek(0)
                content = f.read().decode(encoding)

                # Parse CSV
                csv_reader = csv.DictReader(io.StringIO(content))
                all_rows = list(csv_reader)

            # Get the batch to import
            end_row = min(start_row + batch_size, len(all_rows))
            batch_rows = all_rows[start_row:end_row]

            if not batch_rows:
                return {
                    "imported_row_ids": [],
                    "failed_rows": [],
                    "next_start_row": start_row,
                    "completed": True,
                    "total_rows": len(all_rows),
                }

            # Get table field mapping
            table_model = table.get_model()
            table_fields = {
                field_obj["field"].name.lower().strip(): field_obj["field"]
                for field_obj in table_model.get_field_objects()
            }

            # Adapt rows to table schema
            adapted_rows = []
            failed_rows = []

            for idx, csv_row in enumerate(batch_rows):
                try:
                    adapted_row = {}
                    for csv_col_name, csv_value in csv_row.items():
                        # Match column name (case-insensitive)
                        field_key = csv_col_name.lower().strip()

                        if field_key in table_fields:
                            field = table_fields[field_key]
                            # Use the actual field name from table
                            adapted_row[field.name] = adapt_value(csv_value, field)

                    if adapted_row:  # Only add if we have any values
                        adapted_rows.append(adapted_row)
                except Exception as e:
                    failed_rows.append(
                        {
                            "row_number": start_row + idx + 1,
                            "error": str(e),
                        }
                    )

            # Import rows using the create_rows tool
            import_result = {"created_row_ids": []}
            if adapted_rows:
                try:
                    import_result = create_rows_tool(rows=adapted_rows)
                except Exception as e:
                    return {
                        "error": f"Failed to create rows: {str(e)}",
                        "adapted_rows_count": len(adapted_rows),
                        "failed_rows": failed_rows,
                    }

            # Determine if import is complete
            completed = end_row >= len(all_rows)
            next_start_row = end_row if not completed else start_row

            return {
                "imported_row_ids": import_result.get("created_row_ids", []),
                "imported_count": len(import_result.get("created_row_ids", [])),
                "failed_rows": failed_rows,
                "next_start_row": next_start_row,
                "completed": completed,
                "total_rows": len(all_rows),
                "progress_percentage": int((end_row / len(all_rows)) * 100),
            }

        except UserFile.DoesNotExist:
            return {"error": f"File with ID {file_id} not found or access denied"}
        except Exception as e:
            return {"error": f"Import error: {str(e)}"}

    return import_csv_rows


def adapt_value(csv_value: str, field) -> Any:
    """
    Adapts a CSV value to match the target field type.
    """
    # Handle empty values
    if not csv_value or not csv_value.strip():
        return None

    value = csv_value.strip()
    field_type = field.get_type()

    try:
        if field_type.type == "text" or field_type.type == "long_text":
            return value

        elif field_type.type == "number":
            # Remove commas and convert to number
            clean_value = value.replace(",", "")
            return float(clean_value)

        elif field_type.type == "boolean":
            boolean_true = {"true", "yes", "1", "t", "y"}
            return value.lower() in boolean_true

        elif field_type.type == "date":
            # Try multiple date formats
            date_formats = [
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%d-%m-%Y",
                "%d/%m/%Y",
                "%m-%d-%Y",
                "%m/%d/%Y",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
            ]

            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(value, fmt)
                    # Return ISO format string
                    if field.date_include_time:
                        return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        return parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    continue

            # If no format matched, return None
            return None

        elif field_type.type == "single_select":
            # Check if value matches an existing option
            existing_options = {opt.value for opt in field.select_options.all()}
            if value in existing_options:
                return value
            # If not, return None (or could create new option)
            return None

        elif field_type.type == "multiple_select":
            # Try to split by common delimiters
            delimiters = [",", ";", "|"]
            values = [value]
            for delim in delimiters:
                if delim in value:
                    values = [v.strip() for v in value.split(delim)]
                    break

            # Filter to existing options
            existing_options = {opt.value for opt in field.select_options.all()}
            valid_values = [v for v in values if v in existing_options]
            return valid_values if valid_values else []

        else:
            # For unsupported types, return the raw value
            return value

    except Exception:
        # If adaptation fails, return None
        return None


class ImportCsvRowsToolType(AssistantToolType):
    type = "import_csv_rows"
    thinking_message = "Importing CSV rows..."

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_import_csv_rows_tool(user, workspace, tool_helpers)
