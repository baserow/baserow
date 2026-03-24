from django.urls import path

from .views import (
    AIProviderModelTestView,
    AIProviderOverrideView,
    AIProvidersView,
    AIProviderView,
    AvailableModelsView,
    FeatureDefaultsView,
)

app_name = "baserow.api.ai_provider"

urlpatterns = [
    path("", AIProvidersView.as_view(), name="list"),
    path("<int:provider_id>/", AIProviderView.as_view(), name="item"),
    path(
        "<int:provider_id>/override/",
        AIProviderOverrideView.as_view(),
        name="override",
    ),
    path(
        "models/<int:model_id>/test/",
        AIProviderModelTestView.as_view(),
        name="model_test",
    ),
    path("models/", AvailableModelsView.as_view(), name="available_models"),
    path(
        "feature-defaults/",
        FeatureDefaultsView.as_view(),
        name="feature_defaults",
    ),
]
