from typing import Any
from uuid import uuid4

from django.conf import settings

from baserow.contrib.integrations.core.models import CoreSMTPEmailService
from baserow.core.formula.types import BaserowFormulaObject

from .registries import AgentActionDefaults, AgentActionType


class SMTPEmailAgentActionType(AgentActionType):
    type = "smtp_email"

    def get_defaults(self) -> AgentActionDefaults:
        definitions = [
            ("to_email", "email", "The recipient's email address.", "to_emails"),
            ("subject", "string", "A concise subject for the email.", "subject"),
            (
                "body",
                "string",
                "The complete plain-text email message, ready to send as it is. "
                "Sign it with what you know and never leave a placeholder such as "
                "[Your Name].",
                "body",
            ),
        ]
        inputs, service = (
            [],
            {
                "use_instance_smtp_settings": self.service_type.instance_smtp_is_available(),
                "body_type": "plain",
            },
        )
        for name, input_type, description, field in definitions:
            input_id = str(uuid4())
            inputs.append(
                {
                    "id": input_id,
                    "name": name,
                    "type": input_type,
                    "description": description,
                    "required": True,
                }
            )
            service[field] = BaserowFormulaObject.create(
                f"get('tool_input.{input_id}')", mode="simple"
            )
        return {
            "name": "send_email",
            "description": "Send an email when the user asks to contact someone "
            "or deliver information by email. The recipient receives exactly what "
            "you provide.",
            "inputs": inputs,
            "service": service,
        }

    def get_preview_values(
        self, service: CoreSMTPEmailService, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        sender = (
            {"from_email": settings.FROM_EMAIL, "from_name": ""}
            if service.use_instance_smtp_settings
            else {key: resolved_values[key] for key in ("from_email", "from_name")}
        )
        content = ("to_emails", "cc_emails", "bcc_emails", "subject", "body")
        return {
            **sender,
            **{key: resolved_values[key] for key in content},
            "body_type": service.body_type,
        }
