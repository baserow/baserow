import abc
import time
from typing import Any, Callable

from django.core.paginator import Paginator
from django.db.models import QuerySet

import unicodecsv as csv

from baserow.contrib.database.export.exceptions import ExportJobCanceledException
from baserow.contrib.database.table.models import FieldObject
from baserow.contrib.database.views.filters import AdHocFilters
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.registries import view_type_registry


class FileWriter(abc.ABC):
    """
    A simple file wrapping abstract class which expects it's users to not interact
    with the file but instead write to it via the provided methods. Crucially any
    querysets to be written to the file must be done so via the write_rows method
    as FileWriter implementations perform optimizations when writing querysets in bulk.
    """

    def __init__(self, file):
        self._file = file

    @abc.abstractmethod
    def write_bytes(self, value: bytes):
        """
        Writes the provided bytes straight to the file.

        :param value: The bytes value to write to the file.
        """

    @abc.abstractmethod
    def write(self, value: str, encoding="utf-8"):
        """
        Writes the provided string to the file in the provided encoding.

        :param value: The string to write.
        :param encoding: The encoding to convert the string to before writing.
        """

    @abc.abstractmethod
    def write_rows(
        self,
        queryset: QuerySet,
        write_row: Callable[[Any, bool], None],
        progress_weight: int,
    ):
        """
        A specialized method which knows how to write an entire queryset to the file
        in an optimal way.
        :param queryset: The queryset to write to the file.
        :param write_row: A callable function which takes each row from the queryset in
            turn and writes to the file.
        :param progress_weight: Indicates how much of the progress should count for
            writing the rows in total. This can be used to reduce the total
            percentage if there is some post-processing after writing to the rows
            that must use some of the progress.
        """

    def get_csv_dict_writer(self, headers, **kwargs):
        return csv.DictWriter(self._file, headers, **kwargs)


class PaginatedExportJobFileWriter(FileWriter):
    """
    Uses Django's built-in paginator to write querysets to files in a memory efficient
    manner. Also updates the provided job as it progresses through any queryset writes
    every EXPORT_JOB_UPDATE_FREQUENCY_SECONDS.
    """

    EXPORT_JOB_UPDATE_FREQUENCY_SECONDS = 1

    def __init__(self, file, job):
        super().__init__(file)
        self.job = job
        self.last_check = None

    def update_check(self):
        self.last_check = time.perf_counter()

    def write_bytes(self, value: bytes):
        self._file.write(value)

    def write(self, value: str, encoding="utf-8"):
        self._file.write(value.encode(encoding))

    def write_rows(self, queryset, write_row, progress_weight=100):
        """
        Writes the queryset to the file using the provided write_row callback.
        Every EXPORT_JOB_UPDATE_FREQUENCY_SECONDS will check if the job has been
        cancelled and if so stop writing to the file and will raise a
        ExportJobCanceledException. Finally will also update job.progress_percentage
        every EXPORT_JOB_UPDATE_FREQUENCY_SECONDS as it progresses through writing
        the queryset.

        :param queryset: The queryset to write to the file.
        :param write_row: A callable function which takes each row from the queryset in
            turn and writes to the file.
        :param progress_weight: Indicates how much of the progress should count for
            writing the rows in total. This can be used to reduce the total
            percentage if there is some post-processing after writing to the rows
            that must use some of the progress.
        """

        self.update_check()
        paginator = Paginator(queryset.all(), 2000)
        i = 0
        results = []
        for page in paginator.page_range:
            for row in paginator.page(page).object_list:
                i = i + 1
                is_last_row = i == paginator.count
                result = write_row(row, is_last_row)
                if result is not None:
                    results.append(result)
                self._check_and_update_job(i, paginator.count, progress_weight)
        return results

    def _check_and_update_job(self, current_row, total_rows, progress_weight=100):
        """
        Checks if enough time has passed and if so checks the state of the job and
        updates its progress percentage.
        Will raise a ExportJobCanceledException exception if when a check occurs
        the job has been cancelled.

        :param current_row: An int indicating the current row this export job has
            exported upto
        :param total_rows: An int of the total number of rows this job is exporting.
        """

        current_time = time.perf_counter()
        # We check only every so often as we don't need per row granular updates as the
        # client is only polling every X seconds also.
        enough_time_has_passed = (
            current_time - self.last_check > self.EXPORT_JOB_UPDATE_FREQUENCY_SECONDS
        )
        is_last_row = current_row == total_rows
        if enough_time_has_passed or is_last_row:
            self.update_check()
            self.job.refresh_from_db()
            if self.job.is_cancelled_or_expired():
                raise ExportJobCanceledException()
            else:
                # min is used here because in case of files we get total size from
                # files, but for progress measurement we use size of chunks that might
                # be slightly bigger than the total size of the files
                self.job.progress_percentage = min(
                    current_row / total_rows * progress_weight, 100
                )
                self.job.save()


class QuerysetSerializer(abc.ABC):
    """
    A class knows how to serialize a given queryset and the fields of said queryset to
    a file.
    """

    can_handle_rich_value = False

    def __init__(self, queryset, ordered_field_objects):
        self.queryset = queryset
        self.field_serializers = [lambda row: ("id", "id", row.id)]
        self.ordered_field_objects = ordered_field_objects

        for field_object in ordered_field_objects:
            self.field_serializers.append(self._get_field_serializer(field_object))

    @abc.abstractmethod
    def write_to_file(self, file_writer: FileWriter, **kwargs):
        """
        Writes the queryset to the provided file_writer.

        :param file_writer: The file_writer used write the queryset to.
        :param kwargs: Any kwargs will be passed onto the real non-abstract class.
        """

    @classmethod
    def for_table(cls, table) -> "QuerysetSerializer":
        """
        Generates a queryset serializer for the provided table.
        :param table: The table to serialize.
        :return: A QuerysetSerializer ready to serialize the table.
        """

        model = table.get_model()
        qs = model.objects.all().enhance_by_fields()
        ordered_field_objects = model._field_objects.values()
        return cls(qs, ordered_field_objects)

    @classmethod
    def for_view(cls, view, visible_field_ids_in_order=None) -> "QuerysetSerializer":
        """
        Generates a queryset serializer for the provided view according to it's view
        type and any relevant view settings it might have (filters, sorts,
        hidden columns etc).

        :param view: The view to serialize.
        :param visible_field_ids_in_order: Optionally provide a list of field IDs in
            the correct order. Only those fields will be included in the export.
        :return: A QuerysetSerializer ready to serialize the table.
        """

        view_type = view_type_registry.get_by_model(view.specific_class)
        visible_field_objects_in_view, model = view_type.get_visible_fields_and_model(
            view
        )
        if visible_field_ids_in_order is None:
            fields = visible_field_objects_in_view
        else:
            # Re-order and return only the fields in visible_field_ids_in_order
            field_map = {
                field_object["field"].id: field_object
                for field_object in visible_field_objects_in_view
            }
            fields = [
                field_map[field_id]
                for field_id in visible_field_ids_in_order
                if field_id in field_map
            ]
        qs = ViewHandler().get_queryset(None, view, model=model)
        return cls(qs, fields), visible_field_objects_in_view

    def add_ad_hoc_filters_dict_to_queryset(self, filters_dict, only_by_field_ids=None):
        filters = AdHocFilters.from_dict(filters_dict)
        filters.only_filter_by_field_ids = only_by_field_ids
        self.queryset = filters.apply_to_queryset(self.queryset.model, self.queryset)

    def add_add_hoc_order_by_to_queryset(self, order_by, only_by_field_ids=None):
        self.queryset = self.queryset.order_by_fields_string(
            order_by, only_order_by_field_ids=only_by_field_ids
        )

    def _get_field_serializer(self, field_object: FieldObject) -> Callable[[Any], Any]:
        """
        An internal standard method which generates a serializer function for a given
        field_object. It will delegate to the field_types get_export_value on
        how to convert a given field to a python value to be then written to the file.

        :param field_object: The field object to generate a serializer for.
        :return: A callable function which when given a row will return a tuple of the
            fields database column name, the fields human readable name and finally
            the value of the field in the provided converted to a python value ready
            for export.
        """

        def serializer_func(row):
            value = getattr(row, field_object["name"])

            if value is None:
                result = ""
            else:
                result = field_object["type"].get_export_value(
                    value, field_object, rich_value=self.can_handle_rich_value
                )

            return (
                field_object["name"],
                field_object["field"].name,
                result,
            )

        return serializer_func
