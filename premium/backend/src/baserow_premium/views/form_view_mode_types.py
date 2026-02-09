from baserow.contrib.database.views.registries import FormViewModeType
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler


class FormViewModeTypeSurvey(FormViewModeType):
    type = "survey"

    def before_form_create(self, values: dict, table, user):
        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, user, table.database.workspace
        )

    def before_form_update(self, values: dict, view, user):
        # We do want to allow updates of other attributes of the form, like for example
        # changing the name because it's not obvious to the user that's not possible.
        if "mode" in values:
            LicenseHandler.raise_if_user_doesnt_have_feature(
                PREMIUM, user, view.table.database.workspace
            )
