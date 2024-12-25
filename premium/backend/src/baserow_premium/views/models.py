from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse_lazy

from baserow.contrib.database.fields.models import Field, FileField, SingleSelectField
from baserow.contrib.database.views.models import View
from baserow.core.mixins import HierarchicalModelMixin

OWNERSHIP_TYPE_PERSONAL = "personal"


class KanbanView(View):
    field_options = models.ManyToManyField(Field, through="KanbanViewFieldOptions")
    single_select_field = models.ForeignKey(
        SingleSelectField,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="kanban_view_single_select_field",
        help_text="The single select field related to the options where rows should "
        "be stacked by.",
    )
    card_cover_image_field = models.ForeignKey(
        FileField,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="kanban_view_card_cover_field",
        help_text="References a file field of which the first image must be shown as "
        "card cover image.",
    )

    class Meta:
        db_table = "database_kanbanview"


class KanbanViewFieldOptionsManager(models.Manager):
    """
    The View can be trashed and the field options are not deleted, therefore
    we need to filter out the trashed views.
    """

    def get_queryset(self):
        trashed_Q = Q(kanban_view__trashed=True) | Q(field__trashed=True)
        return super().get_queryset().filter(~trashed_Q)


class KanbanViewFieldOptions(HierarchicalModelMixin, models.Model):
    objects = KanbanViewFieldOptionsManager()
    objects_and_trash = models.Manager()

    kanban_view = models.ForeignKey(KanbanView, on_delete=models.CASCADE)
    field = models.ForeignKey(Field, on_delete=models.CASCADE)
    hidden = models.BooleanField(
        default=True,
        help_text="Whether or not the field should be hidden in the card.",
    )
    # The default value is the maximum value of the small integer field because a newly
    # created field must always be last.
    order = models.SmallIntegerField(
        default=32767,
        help_text="The order that the field has in the view. Lower value is first.",
    )

    def get_parent(self):
        return self.kanban_view

    class Meta:
        db_table = "database_kanbanviewfieldoptions"
        ordering = ("order", "field_id")
        unique_together = ("kanban_view", "field")


class CalendarView(View):
    field_options = models.ManyToManyField(Field, through="CalendarViewFieldOptions")
    date_field = models.ForeignKey(
        Field,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="calendar_view_date_field",
        help_text="One of the supported date fields that "
        "the calendar view will be based on.",
    )
    # TODO Remove null=True in a future release
    ical_public = models.BooleanField(
        null=True,
        default=False,
        db_index=True,
        help_text=("Setting this to `True` will expose ical feed url"),
    )
    # TODO Remove null=True in a future release
    ical_slug = models.SlugField(
        null=True,
        unique=True,
        default=None,
        db_index=True,
        help_text=("Additional slug that allow access to ical format feed"),
    )

    class Meta:
        db_table = "database_calendarview"

    @property
    def ical_feed_url(self) -> str | None:
        if self.ical_slug:
            url_name = "api:database:views:calendar:calendar_ical_feed"
            return (
                f"{settings.PUBLIC_BACKEND_URL}"
                f"{reverse_lazy(url_name, args=(self.ical_slug,))}"
            )


class CalendarViewFieldOptionsManager(models.Manager):
    """
    The View can be trashed and the field options are not deleted, therefore
    we need to filter out the trashed views.
    """

    def get_queryset(self):
        trashed_Q = Q(calendar_view__trashed=True) | Q(field__trashed=True)
        return super().get_queryset().filter(~trashed_Q)


class CalendarViewFieldOptions(HierarchicalModelMixin, models.Model):
    objects = CalendarViewFieldOptionsManager()
    objects_and_trash = models.Manager()

    calendar_view = models.ForeignKey(CalendarView, on_delete=models.CASCADE)
    field = models.ForeignKey(Field, on_delete=models.CASCADE)
    hidden = models.BooleanField(
        default=True,
        help_text="Whether or not the field should be hidden in the card.",
    )
    # The default value is the maximum value of the small integer field because a newly
    # created field must always be last.
    order = models.SmallIntegerField(
        default=32767,
        help_text="The order that the field has in the view. Lower value is first.",
    )

    def get_parent(self):
        return self.calendar_view

    class Meta:
        db_table = "database_calendarviewfieldoptions"
        ordering = ("order", "field_id")
        unique_together = ("calendar_view", "field")


class TimelineView(View):
    class TIMESCALE_OPTIONS(models.TextChoices):
        DAY = "day"
        WEEK = "week"
        MONTH = "month"
        YEAR = "year"

    field_options = models.ManyToManyField(Field, through="TimelineViewFieldOptions")
    start_date_field = models.ForeignKey(
        Field,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="timeline_views_start_date_field",
        help_text="One of the supported date fields that "
        "the timeline view will be use as start date.",
    )
    end_date_field = models.ForeignKey(
        Field,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="timeline_views_end_date_field",
        help_text="One of the supported date fields that "
        "the timeline view will be use as end date.",
    )
    timescale = models.CharField(
        max_length=32,
        choices=TIMESCALE_OPTIONS.choices,
        default=TIMESCALE_OPTIONS.MONTH,
        db_default=TIMESCALE_OPTIONS.MONTH,
        help_text="The timescale that the timeline should be displayed in.",
    )

    class Meta:
        db_table = "database_timelineview"


class TimelineViewFieldOptionsManager(models.Manager):
    """
    The View can be trashed and the field options are not deleted, therefore
    we need to filter out the trashed views.
    """

    def get_queryset(self):
        trashed_Q = Q(timeline_view__trashed=True) | Q(field__trashed=True)
        return super().get_queryset().filter(~trashed_Q)


class TimelineViewFieldOptions(HierarchicalModelMixin, models.Model):
    objects = TimelineViewFieldOptionsManager()
    objects_and_trash = models.Manager()

    timeline_view = models.ForeignKey(TimelineView, on_delete=models.CASCADE)
    field = models.ForeignKey(Field, on_delete=models.CASCADE)
    hidden = models.BooleanField(
        default=True,
        help_text="Whether or not the field should be hidden in the card.",
    )
    # The default value is the maximum value of the small integer field because a newly
    # created field must always be last.
    order = models.SmallIntegerField(
        default=32767,
        help_text="The order that the field has in the view. Lower value is first.",
    )

    def get_parent(self):
        return self.timeline_view

    class Meta:
        db_table = "database_timelineviewfieldoptions"
        ordering = ("order", "field_id")
        unique_together = ("timeline_view", "field")
