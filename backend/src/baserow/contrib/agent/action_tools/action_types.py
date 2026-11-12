from uuid import uuid4

from django.conf import settings

from baserow.contrib.agent.previews import StepPreview, cut
from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import BaserowFormulaException
from baserow.core.formula.exceptions import InvalidRuntimeFormula
from baserow.core.formula.parser.formula_validation_visitor import (
    BaserowFormulaValidationVisitor,
)
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW, BaserowFormulaObject
from baserow.core.services.handler import ServiceHandler
from baserow.core.utils import to_path

from .data_providers import (
    AgentActionDispatchContext,
    agent_action_data_provider_type_registry,
)
from .inputs import build_input_model
from .registries import AgentActionType


class ActionFormulaValidationVisitor(BaserowFormulaValidationVisitor):
    """Validate stable input references without evaluating formulas or fake values."""

    def __init__(self, inputs):
        super().__init__(
            formula_runtime_function_registry,
            agent_action_data_provider_type_registry,
        )
        self.input_ids = {item["id"] for item in inputs}

    def visitFunctionCall(self, ctx, function_name=None):
        result = super().visitFunctionCall(ctx, function_name)
        name = function_name or ctx.func_name().getText().lower()
        if name == "get":
            # Use the validation visitor's literal value so whitespace, comments
            # and parentheses behave exactly as in the shared formula editor.
            # A computed path returns DeferredValue and cannot be checked here.
            argument = ctx.expr()[0].accept(self)
            if not isinstance(argument, str):
                raise InvalidRuntimeFormula(
                    "Action input references must be literal paths."
                )
            provider, *path = to_path(argument)
            if (
                provider != "tool_input"
                or len(path) != 1
                or path[0] not in self.input_ids
            ):
                raise InvalidRuntimeFormula("This action input no longer exists.")
        return result


def get_formula_errors(service, inputs):
    errors = {}
    for formula in service.get_type().formulas_to_resolve(service):
        value = formula.formula
        if not value["formula"] or value.get("mode") == BASEROW_FORMULA_MODE_RAW:
            continue
        try:
            ActionFormulaValidationVisitor(inputs).visit(
                get_parse_tree_for_formula(value["formula"])
            )
        except (BaserowFormulaException, InstanceTypeDoesNotExist):
            errors[formula.key] = "invalid"
    return errors


class SMTPEmailAgentActionType(AgentActionType):
    type = "smtp_email"

    def get_defaults(self):
        definitions = [
            ("to_email", "email", "The recipient's email address.", "to_emails"),
            ("subject", "string", "A concise subject for the email.", "subject"),
            ("body", "string", "The full plain-text email message.", "body"),
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
            "description": "Send an email when the user asks to contact someone or deliver information by email. Use the configured email template and provide the requested inputs.",
            "inputs": inputs,
            "service": service,
        }

    def get_configuration_errors(self, action):
        service = action.service.specific
        errors = ServiceHandler().get_configuration_errors(service, action.agent_id)
        errors.update(get_formula_errors(service, action.inputs))
        if not self.is_available(action.agent.workspace):
            errors["type"] = "unavailable"
        return errors

    def _get_dispatch_context(self, action, arguments):
        self.service_type.raise_if_deactivated(action.agent.workspace)
        values = (
            build_input_model(action.inputs)
            .model_validate(arguments)
            .model_dump(by_alias=True)
        )
        return AgentActionDispatchContext(
            workspace=action.agent.workspace,
            tool_inputs={item["id"]: values[item["name"]] for item in action.inputs},
        )

    def get_preview(self, action, arguments):
        service = action.service.specific
        resolved = self.service_type.resolve_service_formulas(
            service, self._get_dispatch_context(action, arguments)
        )
        if service.use_instance_smtp_settings:
            resolved["from_email"] = settings.FROM_EMAIL
            resolved["from_name"] = ""
        # Explicit allowlist: export-sensitive fields include email content and
        # therefore cannot be used as an approval-preview redaction policy.
        preview_values = {
            key: resolved[key]
            for key in (
                "from_email",
                "from_name",
                "to_emails",
                "cc_emails",
                "bcc_emails",
                "subject",
                "body",
            )
        }
        preview_values["body_type"] = service.body_type
        bounded = cut(preview_values)
        return StepPreview(
            names=bounded, truncated=bounded != preview_values
        ).to_input()

    def dispatch(self, action, arguments):
        return ServiceHandler().dispatch_service(
            action.service.specific,
            self._get_dispatch_context(action, arguments),
            application_id=action.agent_id,
        )
