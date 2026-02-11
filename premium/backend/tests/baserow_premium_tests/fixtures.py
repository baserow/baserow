from baserow.contrib.database.fields.models import Field
from baserow.core.prosemirror.schema import schema
from baserow.core.prosemirror.utils import prosemirror_doc_from_plain_text
from baserow_premium.fields.models import AIField
from baserow_premium.license.models import License, LicenseUser
from baserow_premium.row_comments.models import RowComment
from baserow_premium.views.models import (
    CalendarView,
    CalendarViewFieldOptions,
    KanbanView,
    KanbanViewFieldOptions,
    TimelineView,
    TimelineViewFieldOptions,
)

VALID_ONE_SEAT_LICENSE = (
    # id: "1", instance_id: "1"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjEiLCAidmFsaWRfZnJvbSI6ICIyMDIxLTA4LTI5VDE5OjUyOjU3"
    b"Ljg0MjY5NiIsICJ2YWxpZF90aHJvdWdoIjogIjIwMjEtMDktMjlUMTk6NTI6NTcuODQyNjk2IiwgInBy"
    b"b2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogMSwgImlzc3VlZF9vbiI6ICIyMDIxLTA4LTI5"
    b"VDE5OjUyOjU3Ljg0MjY5NiIsICJpc3N1ZWRfdG9fZW1haWwiOiAiYnJhbUBiYXNlcm93LmlvIiwgImlz"
    b"c3VlZF90b19uYW1lIjogIkJyYW0iLCAiaW5zdGFuY2VfaWQiOiAiMSJ9.e33Z4CxLSmD-R55Es24P3mR"
    b"8Oqn3LpaXvgYLzF63oFHat3paon7IBjBmOX3eyd8KjirVf3empJds4uUw2Nn2m7TVvRAtJ8XzNl-8ytf"
    b"2RLtmjMx1Xkgp5VZ8S7UqJ_cKLyl76eVRtGEA1DH2HdPKu1vBPJ4bzDfnhDPYl4k5z9XSSgqAbQ9WO0U"
    b"5kiI3BYjVRZSKnZMeguAGZ47ezDj_WArGcHAB8Pa2v3HFp5Y34DMJ8r3_hD5hxCKgoNx4AHx1Q-hRDqp"
    b"Aroj-4jl7KWvlP-OJNc1BgH2wnhFmeKHotv-Iumi83JQohyceUbG6j8rDDQvJfcn0W2_ebmUH3TKr-w="
    b"="
)
VALID_100_SEAT_LICENSE_UNTIL_YEAR_2099 = (
    # id: "test-license", instance_id: "1"
    # valid from the year 1000 through the year 2099
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogInRlc3QtbGljZW5zZSIsICJ2YWxpZF9mcm9tIjogIjEwMDAtMDEt"
    b"MDFUMTI6MDA6MDAuMDAwMDAwIiwgInZhbGlkX3Rocm91Z2giOiAiMjA5OS0wMS0wMVQxMjowMDowMC4w"
    b"MDAwMDAiLCAicHJvZHVjdF9jb2RlIjogInByZW1pdW0iLCAic2VhdHMiOiAxMDAsICJpc3N1ZWRfb24i"
    b"OiAiMjAyMS0wOC0yOVQxOTo1Mjo1Ny44NDI2OTYiLCAiaXNzdWVkX3RvX2VtYWlsIjogImJyYW1AYmFz"
    b"ZXJvdy5pbyIsICJpc3N1ZWRfdG9fbmFtZSI6ICJCcmFtIiwgImluc3RhbmNlX2lkIjogIjEifQ==.SoF"
    b"QKxwNjNM-lvJ4iy7d8dc4EmWZagMBzgAmQgUJoGo6FtXaTOILOnc3Tm2uSwZ2MImBeehIff8GPE521-k"
    b"a9-0DDYEX4BYVgpLxLF3gFZxgX0QJgsNsauOjEZH8IGFGX1Asdsll2rNbzYDKz68jG7GgK04Lfn19cQ-"
    b"Qg0Qlgq0gB_7CoUulo73fhCjOZHoH1HAzxh77SbgXxJbDQOYlXqortVvl5vDpNcPTbar4IihBJRgaFTM"
    b"7DjR0On8GCX7j944VkXguiGPdglBXTcqRbPf1qqmZ8jaHrKX6wHYysBJs10OqWqT5p_s8cuRrr0IzLDz"
    b"Ss-q11zuFn-ekeJzo5A=="
)


class PremiumFixtures:
    def create_user(self, *args, **kwargs):
        has_active_premium_license = kwargs.pop("has_active_premium_license", False)
        user = super().create_user(*args, **kwargs)

        if has_active_premium_license:
            self.create_active_premium_license_for_user(user)

        return user

    def create_active_premium_license_for_user(self, user):
        test_license, created = License.objects.get_or_create(
            license=VALID_100_SEAT_LICENSE_UNTIL_YEAR_2099.decode()
        )
        LicenseUser.objects.get_or_create(user=user, license=test_license)

    def remove_all_active_premium_licenses(self, user):
        LicenseUser.objects.filter(user=user).delete()

    def create_premium_license(self, **kwargs):
        if "license" not in kwargs:
            kwargs["license"] = VALID_100_SEAT_LICENSE_UNTIL_YEAR_2099.decode()

        return License.objects.create(**kwargs)

    def create_premium_license_user(self, **kwargs):
        if "user" not in kwargs:
            kwargs["user"] = self.create_user()

        if "license" not in kwargs:
            kwargs["license"] = self.create_premium_license()

        return LicenseUser.objects.create(**kwargs)

    def create_kanban_view(self, user=None, create_options=True, **kwargs):
        if "table" not in kwargs:
            kwargs["table"] = self.create_database_table(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        if "single_select_field" not in kwargs:
            kwargs["single_select_field"] = self.create_single_select_field(
                table=kwargs["table"],
            )

        kanban_view = KanbanView.objects.create(**kwargs)
        if create_options:
            self.create_kanban_view_field_options(kanban_view)
        return kanban_view

    def create_kanban_view_field_options(self, kanban_view, **kwargs):
        return [
            self.create_kanban_view_field_option(kanban_view, field, **kwargs)
            for field in Field.objects.filter(table=kanban_view.table)
        ]

    def create_kanban_view_field_option(self, kanban_view, field, **kwargs):
        field_options, _ = KanbanViewFieldOptions.objects.update_or_create(
            kanban_view=kanban_view, field=field, defaults=kwargs
        )
        return field_options

    def create_calendar_view(self, user=None, create_options=True, **kwargs):
        if "table" not in kwargs:
            kwargs["table"] = self.create_database_table(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        if "date_field" not in kwargs:
            kwargs["date_field"] = self.create_date_field(
                table=kwargs["table"],
            )

        calendar_view = CalendarView.objects.create(**kwargs)
        if create_options:
            self.create_calendar_view_field_options(calendar_view)
        return calendar_view

    def create_calendar_view_field_options(self, calendar_view, **kwargs):
        return [
            self.create_calendar_view_field_option(calendar_view, field, **kwargs)
            for field in Field.objects.filter(table=calendar_view.table)
        ]

    def create_calendar_view_field_option(self, calendar_view, field, **kwargs):
        field_options, _ = CalendarViewFieldOptions.objects.update_or_create(
            calendar_view=calendar_view, field=field, defaults=kwargs
        )
        return field_options

    def create_timeline_view(self, user=None, create_options=True, **kwargs):
        if "table" not in kwargs:
            kwargs["table"] = self.create_database_table(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        if "start_date_field" not in kwargs:
            kwargs["start_date_field"] = self.create_date_field(
                table=kwargs["table"],
            )
        if "end_date_field" not in kwargs:
            kwargs["end_date_field"] = self.create_date_field(
                table=kwargs["table"],
            )

        timeline_view = TimelineView.objects.create(**kwargs)
        if create_options:
            self.create_timeline_view_field_options(timeline_view)
        return timeline_view

    def create_timeline_view_field_options(self, timeline_view, **kwargs):
        return [
            self.create_timeline_view_field_option(timeline_view, field, **kwargs)
            for field in Field.objects.filter(table=timeline_view.table)
        ]

    def create_timeline_view_field_option(self, timeline_view, field, **kwargs):
        if "hidden" not in kwargs:
            kwargs["hidden"] = field.id not in [
                timeline_view.start_date_field_id,
                timeline_view.end_date_field_id,
            ]
        field_options, _ = TimelineViewFieldOptions.objects.update_or_create(
            timeline_view=timeline_view, field=field, defaults=kwargs
        )
        return field_options

    def create_row_comment(self, user, row, comment):
        return RowComment.objects.create(
            user=user,
            table=row.get_parent(),
            row_id=row.id,
            comment=comment,
            message=prosemirror_doc_from_plain_text(comment),
        )

    def create_comment_message_from_plain_text(self, plain_text):
        return prosemirror_doc_from_plain_text(plain_text)

    def create_comment_message_with_mentions(self, mentions):
        return schema.node(
            "doc",
            {},
            [
                schema.node(
                    "paragraph",
                    {},
                    [
                        schema.node(
                            "mention", {"id": mention.id, "label": mention.first_name}
                        )
                        for mention in mentions
                    ],
                )
            ],
        ).to_json()

    def create_ai_field(self, user=None, create_field=True, **kwargs):
        self.set_test_field_kwarg_defaults(user, kwargs)

        # Register the fake generative AI model for testing purposes.
        self.register_fake_generate_ai_type()

        if "ai_generative_ai_type" not in kwargs:
            kwargs["ai_generative_ai_type"] = "test_generative_ai"

        if "ai_generative_ai_model" not in kwargs:
            kwargs["ai_generative_ai_model"] = "test_1"

        if "ai_prompt" not in kwargs:
            kwargs["ai_prompt"] = (
                "'What is your purpose? Answer with a maximum of 10 words.'"
            )

        field = AIField.objects.create(**kwargs)

        if create_field:
            self.create_model_field(kwargs["table"], field)

        return field
