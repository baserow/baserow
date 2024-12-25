from django.db import models

from baserow.core.constants import (
    DATE_FORMAT,
    DATE_FORMAT_CHOICES,
    DATE_TIME_FORMAT,
    DATE_TIME_FORMAT_CHOICES,
)


def get_date_time_format(options, format_type):
    date_format_for_type = DATE_FORMAT[options.date_format][format_type]
    time_format_for_type = DATE_TIME_FORMAT[options.date_time_format][format_type]
    if options.date_include_time:
        format_time = f"{date_format_for_type} {time_format_for_type}"
        return format_time
    else:
        return date_format_for_type


class BaseDateMixin(models.Model):
    def __init__(self, *args, **kwargs) -> None:
        # Add retro-compatibility for the old timezone field.
        if (old_timezone := kwargs.pop("timezone", None)) is not None:
            kwargs["date_force_timezone"] = old_timezone
        super().__init__(*args, **kwargs)

    date_format = models.CharField(
        choices=DATE_FORMAT_CHOICES,
        default=DATE_FORMAT_CHOICES[0][0],
        max_length=32,
        help_text="EU (20/02/2020), US (02/20/2020) or ISO (2020-02-20)",
    )
    date_include_time = models.BooleanField(
        default=False, help_text="Indicates if the field also includes a time."
    )
    date_time_format = models.CharField(
        choices=DATE_TIME_FORMAT_CHOICES,
        default=DATE_TIME_FORMAT_CHOICES[0][0],
        max_length=32,
        help_text="24 (14:30) or 12 (02:30 PM)",
    )
    date_show_tzinfo = models.BooleanField(
        default=False, help_text="Indicates if the timezone should be shown."
    )
    date_force_timezone = models.CharField(
        max_length=255,
        null=True,
        help_text="Force a timezone for the field overriding user profile settings.",
    )

    class Meta:
        abstract = True

    def get_python_format(self):
        """
        Returns the strftime format as a string based on the field's properties. This
        could for example be '%Y-%m-%d %H:%I'.

        :return: The strftime format based on the field's properties.
        :rtype: str
        """

        return self._get_format("format")

    def get_psql_format(self):
        """
        Returns the sql datetime format as a string based on the field's properties.
        This could for example be 'YYYY-MM-DD HH12:MIAM'.

        :return: The sql datetime format based on the field's properties.
        :rtype: str
        """

        return self._get_format("sql")

    def get_psql_type(self):
        """
        Returns the postgresql column type used by this field depending on if it is a
        date or datetime.

        :return: The postgresql column type either 'timestamp' or 'date'
        :rtype: str
        """

        return "timestamp" if self.date_include_time else "date"

    def get_psql_type_convert_function(self):
        """
        Returns the postgresql function that can be used to coerce another postgresql
        type to the correct type used by this field.

        :return: The postgresql type conversion function, either 'TO_TIMESTAMP' or
        'TO_DATE'
        :rtype: str
        """

        return "TO_TIMESTAMP" if self.date_include_time else "TO_DATE"

    def _get_format(self, format_type):
        return get_date_time_format(self, format_type)
