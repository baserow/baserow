from baserow.core.models import Agent


def rename_agent_user(agent: Agent) -> None:
    """
    Gives the agent user its Agent's current name.

    :param agent: The renamed Agent.
    """

    if agent.user is not None:
        agent.user.first_name = agent.name[:150]
        agent.user.save(update_fields=["first_name"])
