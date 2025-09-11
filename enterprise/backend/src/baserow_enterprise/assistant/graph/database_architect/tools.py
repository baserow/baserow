from typing import Any
from baserow_enterprise.assistant.graph.tool import AssistantBaseTool
from pydantic import BaseModel
from .types import DatabaseArchitectToolArgsSchema


class DatabaseArchitectTool(AssistantBaseTool):
    name: str = "database_architect"
    description: str = """
Leverage Baserow's database architect to design and create database schemas. This tool ALWAYS provides complete, working examples and asks thoughtful clarifying questions.

**CRITICAL: Parse user intent for immediate execution:**

**BUILD IMMEDIATELY (set need_approval=false) - only for very explicit requests:**
- Direct commands: "Build me a CRM", "Create an inventory system", "Make a project tracker"
- Explicit build requests: "Please build", "Go ahead and create", "Build it now"
- User says "build first, iterate later" or similar rapid prototyping language

**ASK CLARIFYING QUESTIONS FIRST (set need_approval=true) - DEFAULT behavior:**
- General requests: "I need a database for...", "Help me with...", "Can you design..."
- Exploratory: "What would work for...", "I'm thinking about..."
- Uncertain: "I think I need...", "Maybe we could..."

**Key approach:**
- ALWAYS generate a complete, working example schema to show what's possible
- Ask 1-2 thoughtful questions to refine the design
- Include a note that users can "build this example and iterate" if they prefer
- Show users they have options: refine first OR build and iterate

Use this tool when users mention database design, table structures, data organization, or system architecture.
"""
    args_schema: type[BaseModel] = DatabaseArchitectToolArgsSchema

    def _run_impl(self, instructions: str) -> tuple[str, Any]:
        return instructions, DatabaseArchitectToolArgsSchema(instructions=instructions)
