from django.conf import settings

from itsdangerous import URLSafeTimedSerializer

export_public_view_signer = URLSafeTimedSerializer(
    settings.SECRET_KEY, "export-public-view"
)
