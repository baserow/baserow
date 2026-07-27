from django.urls import path

from .views import (
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
