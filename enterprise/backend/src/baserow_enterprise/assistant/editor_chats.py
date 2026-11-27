"""Save editor turns in ordinary Kuma chats and resolve their original scope on resume."""

import json
from contextlib import ExitStack

from django.db import transaction
from django.utils.translation import gettext as _

from baserow.contrib.integrations.local_baserow.service_filters.handler import (
    resolve_service_filter_target,
)
from baserow.core.chat_runs.exceptions import ChatRunAlreadyActive
from baserow.core.chat_runs.handler import ChatRunHandler

from .actions import run_assistant_action
from .editor_context import resolve_editor_location
from .exceptions import AssistantChatDoesNotExist, EditorGenerationFailed
from .handler import AssistantHandler
from .history import append_turn
from .models import AssistantChat, AssistantChatMessage
from .runs import ASSISTANT_RUN_TYPE


def _check_thread(chat, action, target):
    if not chat:
        return
    if not chat.editor_context or chat.editor_context["action"] != action:
        raise AssistantChatDoesNotExist()
    saved = chat.editor_context["target"]
    if action == "update_service_filters" and "table_id" not in saved:
        # Older filter chats identified only the owning service.
        saved = {**saved, "table_id": target["table_id"]}
    if saved != target:
        raise AssistantChatDoesNotExist()
    active = ChatRunHandler().get_active_run(ASSISTANT_RUN_TYPE, chat.pk)
    if active:
        raise ChatRunAlreadyActive(active.pk)


def run_editor_chat_action(action, ctx, prompt, parameters, profile, chat_uuid):
    if action == "update_service_filters" and parameters.get("table_id") is None:
        service = resolve_service_filter_target(
            ctx, parameters["kind"], parameters["id"], for_update=False
        )
        parameters = {**parameters, "table_id": service.table.pk}
    target = {
        key: parameters[key]
        for key in (
            "workspace_id",
            "database_id",
            "table_id",
            "view_id",
            "field_id",
            "agent_id",
            "kind",
            "id",
        )
        if parameters.get(key) is not None
    }
    handler = AssistantHandler()
    chat = handler.get_existing_chat(ctx.user, ctx.workspace, chat_uuid)
    _check_thread(chat, action, target)
    recent = (
        list(chat.messages.order_by("-id").values("id", "role", "content")[:8])
        if chat
        else []
    )
    last_id = recent[0]["id"] if recent else None
    request = prompt
    if recent:
        request = json.dumps(
            {
                "previous_turns": [
                    {"role": m["role"], "content": m["content"][:2000]}
                    for m in reversed(recent)
                ],
                "request": prompt,
            },
            ensure_ascii=False,
        )
    location, label = resolve_editor_location(ctx, action, target)
    label = parameters.get("field_name") or parameters.get("agent_name") or label
    context = {"action": action, "target": target, "location": location, "label": label}
    with ExitStack() as writes:
        locked = None

        def before_write():
            nonlocal locked
            if locked is not None:
                return
            # Start the transaction after model generation so only applying the turn holds locks.
            writes.enter_context(transaction.atomic())
            existing, created = handler.get_or_create_chat(
                ctx.user, ctx.workspace, chat_uuid
            )
            locked = AssistantChat.objects.select_for_update().get(pk=existing.pk)
            if not created:
                _check_thread(locked, action, target)
            if (
                locked.messages.order_by("-id").values_list("id", flat=True).first()
                != last_id
            ):
                raise EditorGenerationFailed()
            resolve_editor_location(ctx, action, target)

        result = run_assistant_action(
            action, ctx, request, parameters, profile, before_write=before_write
        )
        before_write()
        output = result["result"]
        created_key = {
            "create_database": "database_id",
            "create_table": "table_id",
            "create_view": "view_id",
        }.get(action)
        if created_key in output:
            context["location"], context["label"] = resolve_editor_location(
                ctx, action, {created_key: output[created_key]}
            )
        reply = (
            result["summary"]
            or output.get("instructions")
            or {
                "generate_formula": _("Prepared a formula for the field editor."),
                "generate_ai_field_prompt": _(
                    "Prepared a prompt for the AI field editor."
                ),
                "add_row_color": _("Prepared a conditional row color rule."),
            }.get(action, "")
        )
        locked.messages.create(role=AssistantChatMessage.Role.HUMAN, content=prompt)
        locked.messages.create(role=AssistantChatMessage.Role.AI, content=reply)
        locked.editor_context = context
        if not locked.title:
            locked.title = f"{context['label']} · {prompt}"[
                : AssistantChat.TITLE_MAX_LENGTH
            ]
        details = {
            "editor": action,
            "target": target,
            "label": context["label"],
            "result": output,
            "persisted_change": result["changed"],
        }
        locked.message_history = append_turn(
            locked.message_history,
            prompt,
            json.dumps({"reply": reply, **details}, ensure_ascii=False),
        )
        locked.save(
            update_fields=["title", "editor_context", "message_history", "updated_on"]
        )
    return result
