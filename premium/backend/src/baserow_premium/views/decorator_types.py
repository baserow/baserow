from baserow.contrib.database.views.registries import DecoratorType
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler


class PremiumDecoratorType(DecoratorType):
    def before_create_decoration(self, view, user):
        if user:
            LicenseHandler.raise_if_user_doesnt_have_feature(
                PREMIUM, user, view.table.database.workspace
            )

    def before_update_decoration(self, view_decoration, user):
        if user:
            LicenseHandler.raise_if_user_doesnt_have_feature(
                PREMIUM, user, view_decoration.view.table.database.workspace
            )


class LeftBorderColorDecoratorType(PremiumDecoratorType):
    type = "left_border_color"


class BackgroundColorDecoratorType(PremiumDecoratorType):
    type = "background_color"
