from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from baserow.core.models import UserLogEntry

User = get_user_model()


class AdminDashboardHandler:
    def get_counts_from_delta_range(
        self,
        queryset,
        date_field_name,
        delta_mapping,
        expression="pk",
        now=None,
        distinct=False,
        additional_filters=None,
        include_previous=False,
    ):
        """
        Calculates the count of the queryset for multiple date ranges. The
        `delta_mapping` should be a dict containing a timedelta that will be
        subtracted from the provided now date. The count will be calculated for each
        (now - delta) until now. This will all be done in a single query for better
        performance.

        Example:

        self.get_counts_from_delta_range(
            queryset=User.objects,
            date_field_name="date_joined",
            delta_mapping={
                "24_hours": timedelta(hours=24)
            },
            include_previous=True,
        ) ==
            "24_hours": 3,
            "previous_24_hours": 2
        }

        :param queryset: The base queryset that is used to calculate the counts for.
        :type: queryset: QuerySet
        :param date_field_name: The date or datetime field name in the queryset that
            is used for the range.
        :type date_field_name: str
        :param delta_mapping: The key of this dict must be a unique name and the
            value is the timedelta that is used to calculate the range.
        :type delta_mapping: dict
        :param expression: The expression that is used when doing the count.
        :type expression: str
        :param now: If not provided, the current date will be used. This date is used
            as base for calculating the range which is (now - delta) until now.
        :type now: datetime or None
        :param distinct: Indicates if the results
        :type distinct: bool
        :param additional_filters:
        :type additional_filters: dict
        :param include_previous: Indicates if an additional count of the the range
            before each delta_mapping mapping value must be added to the response
            under the name `previous_{name}`. If the delta is for example 24 hours
            than additionally a count of the range 48 hours before now until 24 hours
            before will be included. This can for example be used to show a
            difference of how will things are performing.
        :type include_previous: bool
        :return: A dict containing the provided `delta_mapping` keys and the values
            are the corresponding counts.
        :rtype: dict
        """

        if not now:
            now = datetime.now(tz=timezone.utc)

        if not additional_filters:
            additional_filters = {}

        def get_count(start, end):
            return Count(
                expression,
                filter=Q(
                    **{
                        f"{date_field_name}__gt": start,
                        f"{date_field_name}__lte": end,
                        **additional_filters,
                    }
                ),
                distinct=distinct,
            )

        aggregations = {}

        for name, delta in delta_mapping.items():
            aggregations[name] = get_count(now - delta, now)

            if include_previous:
                aggregations[f"previous_{name}"] = get_count(
                    now - delta - delta, now - delta
                )

        return queryset.aggregate(**aggregations)

    def get_new_user_counts(self, delta_mapping, now=None, include_previous=False):
        return self.get_counts_from_delta_range(
            queryset=User.objects,
            date_field_name="date_joined",
            delta_mapping=delta_mapping,
            now=now,
            include_previous=include_previous,
        )

    def get_active_user_count(self, delta_mapping, now=None, include_previous=False):
        return self.get_counts_from_delta_range(
            queryset=UserLogEntry.objects,
            date_field_name="timestamp",
            delta_mapping=delta_mapping,
            expression="actor_id",
            now=now,
            distinct=True,
            additional_filters={"action": "SIGNED_IN"},
            include_previous=include_previous,
        )

    def get_new_user_count_per_day(self, delta, now=None):
        """
        Returns the new user count for each day in the provided range. The range is
        calculated based by subtracting the delta from the row until now. (now -
        delta until now).

        :param delta: The timedelta that is subtracted from the now date to
            calculate the range. If for example timedelta(days=14) is provided,
            then the count of the last 14 days is returned.
        :type delta: timedelta
        :param now: If not provided, the current date will be used. This date is used
            as base for calculating the range which is (now - delta) until now. The
            timezone of the object is respected.
        :type now: datetime or None
        :rtype: A list containing a dict for each date including the date and the count.
        :rtype: list
        """

        if not now:
            now = datetime.now(tz=timezone.utc)

        return (
            User.objects.filter(date_joined__gt=now - delta, date_joined__lte=now)
            .extra(
                {"date": "date(date_joined at time zone %s)"},
                select_params=(str(now.tzinfo),),
            )
            .order_by("date")
            .values("date")
            .annotate(count=Count("id"))
        )

    def get_active_user_count_per_day(self, delta, now=None):
        """
        Returns the active user count for each day in the provided range. Someone is
        classified as an active user if they have signed in during the provided date
        range. The range is calculated based by subtracting the delta from the row
        until now. (now - delta until now).

        :param delta: The timedelta that is subtracted from the now date to
            calculate the range. If for example timedelta(days=14) is provided,
            then the count of the last 14 days is returned.
        :type delta: timedelta
        :param now: If not provided, the current date will be used. This date is used
            as base for calculating the range which is (now - delta) until now. The
            timezone of the object is respected.
        :type now: datetime or None
        :rtype: A list containing a dict for each date including the date and the count.
        :rtype: list
        """

        if not now:
            now = datetime.now(tz=timezone.utc)

        return (
            UserLogEntry.objects.filter(
                action="SIGNED_IN", timestamp__gt=now - delta, timestamp__lte=now
            )
            .extra(
                {"date": "date(timestamp at time zone %s)"},
                select_params=(str(now.tzinfo),),
            )
            .order_by("date")
            .values("date")
            .annotate(count=Count("actor_id", distinct=True))
        )
