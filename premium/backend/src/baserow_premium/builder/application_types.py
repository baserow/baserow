from baserow.contrib.builder.application_types import BuilderApplicationType


class PremiumBuilderApplicationType(
    BuilderApplicationType,
):
    @property
    def public_serializer_mixins(self):
        from baserow_premium.api.builder.serializers import (
            PremiumPublicBuilderSerializer,
        )

        return [PremiumPublicBuilderSerializer] + super().public_serializer_mixins
