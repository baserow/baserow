from django.conf import settings

from baserow.api.pagination import raise_page_size_limit_exceeded
from baserow.contrib.database.api.views.grid.utils import parse_non_negative_int
from baserow_premium.api.views.exceptions import InvalidSelectOptionParameter


def prepare_kanban_view_parameters(request):
    # Parse the provided select options from the query parameters. It's possible
    # to only fetch the rows of specific field options and also filter on them.
    all_select_options = request.GET.getlist("select_option")
    included_select_options = {}
    for select_option in all_select_options:
        splitted = select_option.split(",")
        option_settings = {}
        for key, raw in zip(("limit", "offset"), splitted[1:3]):
            value = parse_non_negative_int(raw, -1)
            if value < 0:
                raise InvalidSelectOptionParameter(splitted[0])
            option_settings[key] = value
        included_select_options[splitted[0]] = option_settings

    default_limit = parse_non_negative_int(
        request.GET.get("limit"), min(40, settings.ROW_PAGE_SIZE_LIMIT)
    )
    default_offset = parse_non_negative_int(request.GET.get("offset"), 0)

    limits = [default_limit] + [
        option["limit"]
        for option in included_select_options.values()
        if "limit" in option
    ]
    if max(limits) > settings.ROW_PAGE_SIZE_LIMIT:
        raise_page_size_limit_exceeded(settings.ROW_PAGE_SIZE_LIMIT)

    return included_select_options, default_limit, default_offset
