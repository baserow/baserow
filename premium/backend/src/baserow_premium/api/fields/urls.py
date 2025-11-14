from django.urls import re_path

from .views import AsyncGenerateAIFieldValuesView, GenerateFormulaWithAIView

app_name = "baserow_premium.api.fields"

urlpatterns = [
    re_path(
        r"(?P<field_id>[0-9]+)/generate-ai-field-values/$",
        AsyncGenerateAIFieldValuesView.as_view(),
        name="async_generate_ai_field_values",
    ),
    re_path(
        r"table/(?P<table_id>[0-9]+)/generate-ai-formula/$",
        GenerateFormulaWithAIView.as_view(),
        name="generate_ai_formula",
    ),
]
