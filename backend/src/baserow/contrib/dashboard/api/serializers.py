from baserow.contrib.dashboard.models import Dashboard

MIN_PUBLIC_PASSWORD_LENGTH = 8
MAX_PUBLIC_PASSWORD_LENGTH = 256


class HashPublicPasswordSerializerMixin:
    """
    Replaces the raw `public_password` of a dashboard request with its hash, so the
    handler, the undo/redo params and the audit log only ever see the hash. An
    empty string, or a change of `public` without a password, removes the
    password, exactly like it does for publicly shared views.
    """

    def to_internal_value(self, data):
        internal_value = super().to_internal_value(data)

        raw_public_password = internal_value.pop("public_password", None)
        if raw_public_password is not None or "public" in data:
            internal_value["public_password"] = (
                Dashboard.make_password(raw_public_password)
                if raw_public_password
                else ""  # nosec b105
            )

        return internal_value
