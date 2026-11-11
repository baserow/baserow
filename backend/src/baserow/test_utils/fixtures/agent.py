from uuid import uuid4

from django.contrib.auth.models import AbstractUser

from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
    AgentReplyStatus,
    AgentToolApproval,
)


class AgentApplicationFixtures:
    def create_agent_application(
        self, user: AbstractUser | None = None, **kwargs
    ) -> AgentApplication:
        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace(user=user)
        kwargs.setdefault("name", self.fake.name())
        kwargs.setdefault("order", 0)
        return AgentApplication.objects.create(**kwargs)

    def create_agent_conversation(
        self, user: AbstractUser | None = None, **kwargs
    ) -> AgentConversation:
        if user is None:
            user = self.create_user()
        if "agent" not in kwargs:
            kwargs["agent"] = self.create_agent_application(user=user)
        kwargs.setdefault("uuid", uuid4())
        kwargs.setdefault("title", "Conversation")
        kwargs.setdefault("owner_user", user)
        return AgentConversation.objects.create(**kwargs)

    def create_agent_message(
        self,
        user: AbstractUser | None = None,
        agent: AgentApplication | None = None,
        **kwargs,
    ) -> AgentMessage:
        if "conversation" not in kwargs:
            conversation_kwargs = {"agent": agent} if agent else {}
            kwargs["conversation"] = self.create_agent_conversation(
                user=user, **conversation_kwargs
            )
        kwargs.setdefault("uuid", uuid4())
        kwargs.setdefault("content", "Hello")
        return AgentMessage.objects.create(**kwargs)

    def create_agent_tool_approval(
        self,
        user: AbstractUser | None = None,
        conversation: AgentConversation | None = None,
        **kwargs,
    ) -> AgentToolApproval:
        """
        Create a pending approval, in a new waiting reply unless one is given.

        :param user: The owner of the new reply's conversation, when none is given.
        :param conversation: The conversation of the new reply.
        :return: The created approval.
        """

        if "reply" not in kwargs:
            reply_kwargs = {"conversation": conversation} if conversation else {}
            kwargs["reply"] = self.create_agent_message(
                user=user,
                role=AgentMessage.Role.ASSISTANT,
                status=AgentReplyStatus.WAITING,
                **reply_kwargs,
            )
        kwargs.setdefault("tool_call_id", f"call_{uuid4().hex}")
        kwargs.setdefault("step_id", str(uuid4()))
        kwargs.setdefault("pause", 1)
        kwargs.setdefault("tool_name", "create_rows")
        return AgentToolApproval.objects.create(**kwargs)
