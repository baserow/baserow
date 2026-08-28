from django.urls import path

from .views import (
    AIProviderFeaturesView,
    AIProviderFeatureView,
    AIProviderModelDiscoveryView,
    AIProviderModelsTestView,
    AIProviderModelsView,
    AIProviderModelView,
    AIProvidersView,
    AIProviderTypesView,
    AIProviderView,
)

app_name = "baserow.api.ai_provider"

urlpatterns = [
    path("", AIProvidersView.as_view(), name="list"),
    path("types/", AIProviderTypesView.as_view(), name="types"),
    path("features/", AIProviderFeaturesView.as_view(), name="features"),
    path(
        "features/<str:feature_type>/",
        AIProviderFeatureView.as_view(),
        name="feature_item",
    ),
    path("<int:provider_id>/", AIProviderView.as_view(), name="item"),
    path(
        "<int:provider_id>/models/",
        AIProviderModelsView.as_view(),
        name="create_model",
    ),
    path(
        "models/discover/",
        AIProviderModelDiscoveryView.as_view(),
        name="discover_models",
    ),
    path("models/test/", AIProviderModelsTestView.as_view(), name="test_models"),
    path("models/<int:model_id>/", AIProviderModelView.as_view(), name="model_item"),
]
