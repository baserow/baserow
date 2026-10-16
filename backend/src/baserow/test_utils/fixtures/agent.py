from uuid import uuid4

from django.contrib.auth.models import AbstractUser

from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
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
        if "agent" not in kwargs:
            kwargs["agent"] = self.create_agent_application(user=user)
        kwargs.setdefault("uuid", uuid4())
        kwargs.setdefault("title", "Conversation")
        kwargs.setdefault("owner_user", user)
        kwargs.setdefault("initiated_by", user)
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
        kwargs.setdefault("author_user", user)
        return AgentMessage.objects.create(**kwargs)
