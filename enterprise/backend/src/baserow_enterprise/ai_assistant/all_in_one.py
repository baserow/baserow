from collections import defaultdict
from datetime import datetime, timezone
import itertools
import json
import os
from zoneinfo import ZoneInfo
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from django.conf import settings
from pydantic import BaseModel, Field
from langsmith import traceable

from typing import Annotated, List, Literal, Optional
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from typing_extensions import TypedDict
from langchain.chat_models import init_chat_model
from langgraph.graph.message import AnyMessage, add_messages, MessagesState
from langchain_core.output_parsers import StrOutputParser
import yaml

from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.models import View
from baserow_enterprise.ai_assistant.models import AssistantChat
from baserow_enterprise.ai_assistant.tools.documentation_lookup import (
    DocumentationLookupTool,
)
from baserow_enterprise.ai_assistant.tools.row_tools import DynamicRowToolFactory
from baserow_enterprise.ai_assistant.tools.table_finder import (
    TableFinderTool,
    TableURLTool,
)
from baserow_enterprise.ai_assistant.tools.view_tools import DynamicViewToolFactory
from asgiref.sync import sync_to_async
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.models import Workspace

# Enable LangSmith tracing by setting environment variables
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_PROJECT"] = "Baserow Assistant"


def update_dialog_stack(left: list[str], right: Optional[str]) -> list[str]:
    """Push or pop the state."""

    if right is None:
        return left
    if right == "__pop__":
        return left[:-1]
    return left + [right]


class State(MessagesState):
    title: str = Field(help="The title of the chat conversation.")
    # dialog_state: Annotated[
    #     list[
    #         Literal[
    #             "assistant",
    #             # "navigator",
    #             # "filter_builder",
    #         ]
    #     ],
    #     update_dialog_stack,
    # ]
    latest_action_is_undoable: bool = Field(
        default=False, help="Whether the latest action is undoable."
    )


class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    @traceable(name="Assistant.__call__")
    async def __call__(self, state: State, config: RunnableConfig):
        while True:
            last_message = state["messages"][-1]
            result = await self.runnable.ainvoke(state)

            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}


class CompleteOrEscalate(BaseModel):
    """A tool to mark the current task as completed and/or to escalate control of the dialog to the main assistant,
    who can re-route the dialog based on the user's needs."""

    cancel: bool = Field(
        default=False,
        help="Whether to cancel the current task and return control to the main assistant.",
    )
    finished: bool = Field(
        default=False,
        help="Whether the current task is finished correctly and the response can be sent to the user.",
    )
    reason: str = Field(
        default="", help="The reason for canceling or finishing the task."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "cancel": True,
                "finished": False,
                "reason": "User changed their mind about the current task.",
            },
            "example 2": {
                "cancel": False,
                "finished": True,
                "reason": "I have fully completed the task.",
            },
            "example 3": {
                "cancel": False,
                "finished": False,
                "reason": "I need to search the user's emails or calendar for more information.",
            },
        }


# navigator_prompt = ChatPromptTemplate.from_messages(
#     [
#         (
#             "system",
#             """
#             You are a specialized assistant for navigating tables in Baserow.
#             The primary assistant delegates work to you whenever it needs help to navigate the user to the correct page.
#             The page could be a database table or the workspace dashboard.

#             If you find one or more tables, you're task can be considered finished. It will up to the user to decide which table to navigate to
#             or make additional requests to filter down the tables.
#             If the user needs help, and none of your tools are appropriate for it, then 'CompleteOrEscalate' the dialog to the host assistant.
#             Do not waste the user's time. Do not make up invalid tools or functions. Do not alter data returned by the tools in any way.

#             Base address for URLs: {base_frontend_address}
#             """.format(
#                 base_frontend_address=settings.PUBLIC_WEB_FRONTEND_URL
#             ),
#         ),
#         ("placeholder", "{messages}"),
#     ]
# )

# navigator_tools = [TableFinderTool()]
# navigator_llm = init_chat_model(model="gpt-4o-mini", temperature=0.3)
# navigator_runnable = navigator_prompt | navigator_llm.bind_tools(
#     navigator_tools + [CompleteOrEscalate]
# )


# view_expert_prompt = ChatPromptTemplate.from_messages(
#     [
#         (
#             "system",
#             """
#             You are a specialized assistant for creating filters in Baserow's views.
#             The primary assistant delegates work to you whenever it needs help to work on a specific view in a table.

#             If the user needs help, and none of your tools are appropriate for it, then 'CompleteOrEscalate' the dialog
#             to the host assistant.
#             Do not waste the user's time. Do not make up invalid tools or functions. Do not alter in any way names and URLs returned by the tools.
#             """,
#         ),
#         ("placeholder", "{messages}"),
#     ]
# )

# view_expert_tools = []
# view_expert_llm = init_chat_model(model="gpt-4o-mini", temperature=0.3)
# view_expert_runnable = view_expert_prompt | view_expert_llm.bind_tools(
#     view_expert_tools + [CompleteOrEscalate]
# )


# class ToNavigatorAssistant(BaseModel):
#     """Transfers work to the navigator assistant for handling navigation-related requests."""

#     request: str = Field(
#         description="Any necessary followup questions the navigator assistant should clarify before proceeding."
#     )


# class ToViewExpertAssistant(BaseModel):
#     """Transfers work to the view expert assistant for handling view-related requests."""

#     table_id: int = Field(description="The ID of the database table to work on.")
#     view_id: Optional[int] = Field(
#         description="The ID of the view to work on. If None, the assistant should clarify which view to use or ask the user to create a new one."
#     )
#     request: str = Field(
#         description="Any necessary followup questions the view expert assistant should clarify before proceeding."
#     )

#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "table_id": 1,
#                 "view_id": 2,
#                 "request": "Do you want to apply any filters to this view?",
#             }
#         }


BASEROW_PERSONALITY_PROMPT = """
You are Baserow Assistant, a knowledgeable and helpful AI assistant for Baserow, the open-source no-code database platform.
You help users work efficiently with their databases, tables, views, and data.
Be professional, clear, and friendly. Focus on providing practical, actionable solutions.

<writing_style>
Use clear, straightforward language.
Avoid unnecessary jargon or acronyms unless they are commonly understood in the database context.
Use sentence case for all text, including headings and titles.
Be concise but thorough in your explanations.
Focus on actionable guidance that users can immediately apply.
</writing_style>
""".strip()

ROOT_SYSTEM_PROMPT = (
    """
<agent_info>\n"""
    + BASEROW_PERSONALITY_PROMPT
    + """

If the user requires to navigate to some other resource, please use the navigation tools like the table finder tool.
If the user requires to create or update a view or ask some questions about Baserow concepts, delegate to the specialized assistants.
The user is not aware of the different specialized assistants, so do not mention them; just quietly delegate through function calls. "
Provide assistance honestly and transparently, acknowledging any limitations.
Guide users to simple, practical solutions. Think step-by-step.
When troubleshooting, ask for specific error messages or describe what's expected vs. what's happening.

Avoid suggesting things the user has already tried.
Be clear and unambiguous without unnecessary verbosity.
Stay professional and helpful, focusing on the user's database needs.
</agent_info>

<format_instructions>
You can use light Markdown formatting for readability.
Present data in tables when appropriate.
Use bullet points for lists.
</format_instructions>

TOOL USAGE RULES - CRITICAL
1. **ALWAYS use tools for ANY request that matches a tool's capability**
   - Even if similar information exists in chat history
   - Even if you discussed this exact topic before
   - Even if the user says "as we discussed" or "like before"

2. **NEVER use chat history as a substitute for tool calls**
   - Chat history may be outdated, incomplete, or context-specific
   - Previous tool results are NOT valid for new requests
   - Each request must be treated as fresh/independent

3. **Only skip tool usage when:**
   - No available tool can handle the request
   - The request is explicitly about the conversation itself (e.g., "what did I just ask?")
   - The request is for clarification of your previous response


CRITICAL GUIDELINES FOR BASEROW KNOWLEDGE QUESTIONS:
- For navigation tasks → Use specialized tools like the table_finder tool
- For view-related tasks → Use specialized view expert assistant  
- For questions about how Baserow works, features, concepts, or usage → MUST use documentation_lookup tool
- NEVER use pretrained knowledge to answer questions about Baserow functionality
- If information is not available in the documentation, say "I don't have that information in the documentation"
- Be honest about limitations. Never ever guess or improvise or use pre-trained data to answer Baserow questions.
- Answers always need to be based on the documentation.
- Always assume the question is about Baserow. If it's not or is ambiguous, clarify the context before responding.
- If the question is clearly not about Baserow, answer that you cannot assist with that.
- Never ever use the history for navigation tasks or for URLs inside Baserow. Always call the appropriate tools.
- When URLs are returned by tools, always include them in your markdown response. Don't modify the URLs.

WHEN TO USE NAVIGATE TOOLS:
- Every time the user intent is to navigate to a specific table or resource.
- Never make up URLs yourself.

WHEN TO USE THE CHAT HISTORY:
- Only for documentation questions or factual clarifications
- Never use the history when you're supposed to call a tool for the task.
- Things can change in the UI outside of your knowledge, so always call the appropriate tools to ensure accuracy.

WHEN TO USE DOCUMENTATION_LOOKUP (instead of pretrained knowledge):
- Questions about Baserow features, concepts, or capabilities
- "How do I..." questions about Baserow functionality
- Formula syntax, functions, and examples
- Field types, views, permissions, integrations
- Step-by-step procedures and best practices
- API usage and configuration guidance
- Any explanation of how Baserow works

WHEN NOT TO USE DOCUMENTATION_LOOKUP:
- Navigation requests → Use the table_finder tool to find a table by name
- Current workspace/table context → Use interface tools
- View configuration tasks → Use view expert assistant

You can help with:
- Navigating within the current Baserow interface (always use tools, never look at the message history)
- Finding tables and databases in the current workspace  
- Looking up documented Baserow features and procedures
- Providing step-by-step guidance based on official documentation

Provide assistance honestly and transparently, acknowledging when information is not available.
Guide users to simple, practical solutions based on documented best practices.
When troubleshooting, ask for specific error messages or describe what's expected vs. what's happening.

WORKFLOW FOR BASEROW KNOWLEDGE QUESTIONS:
1. Determine if question is about interface → Use specialized assistant
2. If the question is about navigation -> Use table_finder tool
3. If question is about Baserow concepts/features → Use documentation_lookup
4. Say "Let me check the documentation for that information"
5. Use documentation_lookup with appropriate context
6. Provide answer ONLY based on documentation results
7. If no documentation found, say "I don't have that information in the documentation"

EXAMPLES of CORRECT routing:
User: "Go to the users table" → Akways use the table finder tool (NOT documentation)
User: "How do I write a formula?" → "Let me check the documentation for formula information" + documentation_lookup
User: "What field types are available?" → "Let me look up the available field types" + documentation_lookup
User: "Create a new view" → Use view expert assistant (NOT documentation)
User: "How do permissions work in Baserow?" → Use documentation_lookup with context="security"
</agent_info>

If the user asks for instructions, base your response only on the available documentation. 
Do not make up instructions or provide information that is not returned by the available tools. Never assume other tools work the same way.

CONTEXT:

FRONTEND LOCATION:
{ui_context}

CURRENT USER:
ID: {user_id}
Email: {user_email}
Name: {user_name}

CURRENT DATE:
{current_date}

TIMEZONE:
{timezone}
"""
)


async def get_primary_assistant_runnable(user, context: dict = None):
    primary_assistant_tools = [
        DocumentationLookupTool(),
        TableFinderTool(),
        TableURLTool(),
    ]
    context = context or {}

    timezone = context.get("timezone", "UTC")
    if timezone:
        user.profile.timezone = timezone

    table_id = context.get("table_id")
    if table_id:
        table = await Table.objects.select_related("database__workspace").aget(
            pk=table_id
        )
        primary_assistant_tools.extend(
            [
                await DynamicRowToolFactory.create_rows_tool(user, table),
                await DynamicRowToolFactory.update_rows_tool(user, table),
                await DynamicRowToolFactory.list_rows_tool(user, table),
                await DynamicViewToolFactory.create_view_tool(user, table),
            ]
        )

    view_id = context.get("view_id")
    if view_id:
        view = await sync_to_async(
            lambda: View.objects.select_related("table__database__workspace")
            .get(pk=view_id)
            .specific
        )()
        primary_assistant_tools.extend(
            [
                await DynamicViewToolFactory.update_view_tool(user, view),
                # TODO: ensure the view type can filter, sort, group by
                await DynamicViewToolFactory.set_filters_tool(user, view),
                await DynamicViewToolFactory.set_sorts_tool(user, view),
                await DynamicViewToolFactory.set_group_bys_tool(user, view),
                await DynamicViewToolFactory.set_colors_tool(user, view),
            ]
        )

    @sync_to_async
    def get_databases_and_tables():
        workspace_id = context.get("workspace_id")
        if not workspace_id:
            return
        tables = (
            TableHandler()
            .list_workspace_tables(user, Workspace.objects.get(pk=workspace_id))
            .order_by("database_id")
        )
        result = []
        for _, db_tables in itertools.groupby(tables, lambda t: t.database_id):
            ts = list(db_tables)
            db = ts[0].database
            result.append(
                {
                    "id": db.id,
                    "name": db.name,
                    "tables": [
                        {
                            "id": t.id,
                            "name": t.name,
                        }
                        for t in ts
                    ],
                }
            )
        return result

    primary_assistant_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                ROOT_SYSTEM_PROMPT.format(
                    ui_context="\n- ".join(f"{k}: {v}" for k, v in context.items()),
                    user_id=user.id,
                    user_email=user.email,
                    user_name=user.first_name,
                    current_date=datetime.now(tz=ZoneInfo(timezone)).isoformat(),
                    timezone=timezone,
                    # databases_and_tables=yaml.dump(await get_databases_and_tables()),
                ),
            ),
            ("placeholder", "{messages}"),
        ]
    )
    primary_assistant_llm = init_chat_model(model="gpt-4.1", temperature=0.3)
    primary_assistant_runnable = (
        primary_assistant_prompt
        | primary_assistant_llm.bind_tools(primary_assistant_tools)
    )
    return primary_assistant_runnable, primary_assistant_tools


from typing import Callable

from langchain_core.messages import ToolMessage


def create_entry_node(assistant_name: str, new_dialog_state: str) -> Callable:
    @traceable(name=f"entry_node_{assistant_name}")
    def entry_node(state: State) -> dict:
        tool_call_id = state["messages"][-1].tool_calls[0]["id"]
        return {
            "messages": [
                ToolMessage(
                    content=f"The assistant is now the {assistant_name}. Reflect on the above conversation between the host assistant and the user."
                    f" The user's intent is unsatisfied. Use the provided tools to assist the user. Remember, you are {assistant_name},"
                    " actions are not complete until after you have successfully invoked the appropriate tool."
                    " If the user changes their mind or needs help for other tasks, call the CompleteOrEscalate function to let the primary host assistant take control."
                    " Do not mention who you are - just act as the proxy for the assistant.",
                    tool_call_id=tool_call_id,
                )
            ],
            "dialog_state": new_dialog_state,
        }

    return entry_node


from typing import Literal

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition


from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda

from langgraph.prebuilt import ToolNode


@traceable(name="handle_tool_error")
def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )


@traceable(name="pop_dialog_state")
def pop_dialog_state(state: State) -> dict:
    """Pop the dialog stack and return to the main assistant.

    This lets the full graph explicitly track the dialog flow and delegate control
    to specific sub-graphs.
    """
    messages = []
    if state["messages"][-1].tool_calls:
        # Note: Doesn't currently handle the edge case where the llm performs parallel tool calls
        messages.append(
            ToolMessage(
                content="Resuming dialog with the host assistant. Please reflect on the past conversation and assist the user as needed.",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"],
            )
        )
    return {
        "dialog_state": "__pop__",
        "messages": messages,
    }


@traceable(name="route_primary_assistant")
def route_primary_assistant(
    state: State,
):
    route = tools_condition(state)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        # if tool_calls[0]["name"] == ToNavigatorAssistant.__name__:
        #     return "enter_navigator"
        # if tool_calls[0]["name"] == ToViewExpertAssistant.__name__:
        #     return "enter_view_expert"
        # else:
        return "primary_assistant_tools"
    raise ValueError("Invalid route")


TITLE_GENERATION_PROMPT = """
You are an expert in crisp conversation titles.
Given the brief below, output one title that:
– Capture the core intent of the conversation in ≤ 8 words.
– Use clear, action-oriented language (gerund verbs up front where possible).
– Avoid jargon.
– Sound friendly but professional (imagine a Slack channel name).
– Use sentence case where the first letter must be capitalized.
– Do not use empty adjectives.
Respond with the title only—no explanations.
""".strip()


def find_last_message_of_type(messages, message_type):
    return next(
        (msg for msg in reversed(messages) if isinstance(msg, message_type)), None
    )


@traceable(name="title_generator_node")
async def title_generator_node(state: State, config: RunnableConfig) -> dict:
    if state.get("title", None):
        return

    title_generator_llm = init_chat_model(
        model="gpt-4.1-nano", temperature=0.7, max_completion_tokens=100
    )
    title_generator_prompt = ChatPromptTemplate.from_messages(
        [("system", TITLE_GENERATION_PROMPT), ("user", "{user_input}")]
    )
    runnable = title_generator_prompt | title_generator_llm | StrOutputParser()
    last_human_message = find_last_message_of_type(state["messages"], HumanMessage)
    generated_title = await runnable.ainvoke({"user_input": last_human_message})

    return {"title": generated_title.strip().capitalize()}


# Each delegated workflow can directly respond to the user
# When the user responds, we want to return to the currently active workflow
@traceable(name="route_to_workflow")
def route_to_workflow(
    state: State,
) -> Literal["title_generator", "primary_assistant"]:
    """If we are in a delegated state, route directly to the appropriate assistant."""

    dialog_state = state.get("dialog_state")
    if not dialog_state:
        return "title_generator"
    return dialog_state[-1]


async def get_enhanced_graph(user, context):
    """
    Enhanced version of get_graph with visualization support.
    Replace the original get_graph() function with this.
    """
    from langgraph.graph import StateGraph, START, END
    from langgraph.prebuilt import tools_condition
    from .enhanced_tools import EnhancedToolNode

    builder = StateGraph(State)

    def route_agent(agent_name: str, safe_tools):
        def router(state: State):
            route = tools_condition(state)
            if route == END:
                return END
            tool_calls = state["messages"][-1].tool_calls
            did_cancel, did_finished = False, False
            for tc in tool_calls:
                if tc["name"] != CompleteOrEscalate.__name__:
                    continue
                did_cancel = tc.get("cancel", True)
                did_finished = tc.get("finished", False)
                break
            if did_finished:
                return END
            if did_cancel:
                return "leave_skill"
            safe_toolnames = [t.name for t in safe_tools]
            if all(tc["name"] in safe_toolnames for tc in tool_calls):
                return f"{agent_name}_tools"
            return f"{agent_name}_sensitive_tools"

        return router

    # Navigator with enhanced tools
    # builder.add_node(
    #     "enter_navigator",
    #     create_entry_node("Navigator assistant", "navigator"),
    # )
    # builder.add_node(
    #     "navigator",
    #     Assistant(navigator_runnable),
    # )

    # # Use enhanced tool node for navigator
    # builder.add_node(
    #     "navigator_tools",
    #     EnhancedToolNode(navigator_tools),
    # )

    # builder.add_edge("enter_navigator", "navigator")
    # builder.add_edge("navigator_tools", "navigator")

    # builder.add_conditional_edges(
    #     "navigator",
    #     route_agent("navigator", navigator_tools),
    #     ["navigator_tools", "leave_skill", END],
    # )

    # View expert (unchanged)
    # builder.add_node(
    #     "enter_view_expert",
    #     create_entry_node("View expert assistant", "view_expert"),
    # )
    # builder.add_node(
    #     "view_expert",
    #     Assistant(view_expert_runnable),
    # )
    # builder.add_node(
    #     "view_expert_tools",
    #     create_tool_node_with_fallback(view_expert_tools),
    # )
    # builder.add_edge("enter_view_expert", "view_expert")
    # builder.add_edge("view_expert_tools", "view_expert")
    # builder.add_conditional_edges(
    #     "view_expert",
    #     route_agent("view_expert", view_expert_tools),
    #     ["view_expert_tools", "leave_skill", END],
    # )

    # Leave skill and primary assistant (unchanged)
    builder.add_node("leave_skill", pop_dialog_state)
    builder.add_edge("leave_skill", "primary_assistant")

    # Title generator (runs in parallel with primary_assistant)
    builder.add_node("title_generator", title_generator_node)

    # Create a custom Assistant class that filters navigation messages
    class RootNode:
        def __init__(self, runnable: Runnable):
            self.runnable = runnable

        def _construct_messages(self, state):
            # Filter out messages that are not part of the conversation window.
            conversation_window = state["messages"]

            # `assistant` messages must be contiguous with the respective `tool` messages.
            tool_result_messages = {
                message.tool_call_id: message
                for message in conversation_window
                if isinstance(message, ToolMessage)
            }

            history = []
            for message in conversation_window:
                if isinstance(message, HumanMessage):
                    history.append(HumanMessage(content=message.content, id=message.id))
                elif isinstance(message, AIMessage):
                    # Filter out tool calls without a tool response, so the completion doesn't fail.
                    tool_calls = [
                        tool
                        for tool in message.tool_calls
                        if tool["id"] in tool_result_messages
                    ]

                    history.append(
                        AIMessage(
                            content=message.content,
                            tool_calls=tool_calls,
                            id=message.id,
                        )
                    )

                    # Append associated tool call messages.
                    for tool_call in tool_calls:
                        tool_call_id = tool_call["id"]
                        result_message = tool_result_messages[tool_call_id]
                        history.append(
                            ToolMessage(
                                content=result_message.content,
                                tool_call_id=tool_call_id,
                                id=result_message.id,
                            )
                        )

            return history

        @traceable(name="NavigationFilteredAssistant.__call__")
        async def __call__(self, state: State, config: RunnableConfig):
            history = self._construct_messages(state)

            result = await self.runnable.ainvoke({"messages": history})
            return {"messages": result}

    (
        primary_assistant_runnable,
        primary_assistant_tools,
    ) = await get_primary_assistant_runnable(user, context)
    builder.add_node("primary_assistant", RootNode(primary_assistant_runnable))
    builder.add_node(
        "primary_assistant_tools",
        EnhancedToolNode(primary_assistant_tools),
    )

    # Custom routing function to check if TableFinderTool found tables and go directly to END
    @traceable(name="route_after_primary_tools")
    def route_after_primary_tools(state: State):
        """Route after primary assistant tools execute - check if TableFinderTool found tables."""

        return "primary_assistant"

    # Use conditional edge from tools instead of direct edge
    builder.add_conditional_edges(
        "primary_assistant_tools", route_after_primary_tools, ["primary_assistant", END]
    )

    builder.add_conditional_edges(
        "primary_assistant",
        route_primary_assistant,
        [
            "primary_assistant_tools",
            # "enter_navigator",
            # "enter_view_expert",
            END,
        ],
    )

    # Use the new routing function
    builder.add_conditional_edges(START, route_to_workflow)
    builder.add_edge("title_generator", "primary_assistant")
    return builder
