from rest_framework import serializers


class HasSecretField(serializers.BooleanField):
    """
    A read-only boolean that reports whether a write-only credential is set,
    without disclosing its value. Used in place of the credential itself in
    integration response serializers.
    """

    def __init__(self, secret_field_name: str, **kwargs):
        self.secret_field_name = secret_field_name
        kwargs["read_only"] = True
        kwargs.setdefault(
            "help_text",
            f"Whether the `{secret_field_name}` is set. The value itself is "
            f"write-only and is never returned.",
        )
        super().__init__(**kwargs)

    def get_attribute(self, instance):
        return bool(getattr(instance, self.secret_field_name, None))
