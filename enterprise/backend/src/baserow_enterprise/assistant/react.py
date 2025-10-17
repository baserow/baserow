from typing import TYPE_CHECKING, Any, Callable, Literal

import dspy
from dspy.adapters.types.tool import Tool
from dspy.predict.react import _fmt_exc
from dspy.primitives.module import Module
from dspy.signatures.signature import ensure_signature
from litellm import ContextWindowExceededError
from loguru import logger

from .types import ToolsUpgradeResponse

if TYPE_CHECKING:
    from dspy.signatures.signature import Signature


# Variant of dspy.predict.react.ReAct that accepts a "meta-tool":
# a callable that can produce tools at runtime (e.g. per-table schemas).
# This lets a single ReAct instance handle many different table signatures
# without creating a new agent for each request.


class ReAct(Module):
    def __init__(
        self, signature: type["Signature"], tools: list[Callable], max_iters: int = 100
    ):
        """
        ReAct stands for "Reasoning and Acting," a popular paradigm for building
        tool-using agents. In this approach, the language model is iteratively provided
        with a list of tools and has to reason about the current situation. The model
        decides whether to call a tool to gather more information or to finish the task
        based on its reasoning process. The DSPy version of ReAct is generalized to work
        over any signature, thanks to signature polymorphism.

        Args:
            signature: The signature of the module, which defines the input and output
            of the react module. tools (list[Callable]): A list of functions, callable
            objects, or `dspy.Tool` instances. max_iters (Optional[int]): The maximum
            number of iterations to run. Defaults to 10.

        Example:

        ```python def get_weather(city: str) -> str:
            return f"The weather in {city} is sunny."

        react = dspy.ReAct(signature="question->answer", tools=[get_weather]) pred =
        react(question="What is the weather in Tokyo?")
        """

        super().__init__()
        self.signature = signature = ensure_signature(signature)
        self.max_iters = max_iters

        tools = [t if isinstance(t, Tool) else Tool(t) for t in tools]
        tools = {tool.name: tool for tool in tools}
        outputs = ", ".join([f"`{k}`" for k in signature.output_fields.keys()])

        tools["finish"] = Tool(
            func=lambda: "Completed.",
            name="finish",
            desc=f"Marks the task as complete. That is, signals that all information for producing the outputs, i.e. {outputs}, are now available to be extracted.",
            args={},
        )

        self.tools = tools
        self.react = self._build_react_module()
        self.extract = self._build_fallback_module()

    def _build_instructions(self) -> list[str]:
        signature = self.signature
        inputs = ", ".join([f"`{k}`" for k in signature.input_fields.keys()])
        outputs = ", ".join([f"`{k}`" for k in signature.output_fields.keys()])
        instr = [f"{signature.instructions}\n"] if signature.instructions else []

        instr.extend(
            [
                f"You are an Agent. In each episode, you will be given the fields {inputs} as input. And you can see your past trajectory so far.",
                f"Your goal is to use one or more of the supplied tools to collect any necessary information for producing {outputs}.\n",
                "To do this, you will interleave next_thought, next_tool_name, and next_tool_args in each turn, and also when finishing the task.",
                "After each tool call, you receive a resulting observation, which gets appended to your trajectory.\n",
                "When writing next_thought, you may reason about the current situation and plan for future steps.",
                "When selecting the next_tool_name and its next_tool_args, the tool must be one of:\n",
            ]
        )

        for idx, tool in enumerate(self.tools.values()):
            instr.append(f"({idx + 1}) {tool}")
        instr.append(
            "When providing `next_tool_args`, the value inside the field must be in JSON format"
        )
        return instr

    def _build_react_module(self) -> type[Module]:
        instructions = self._build_instructions()
        react_signature = (
            dspy.Signature({**self.signature.input_fields}, "\n".join(instructions))
            .append("trajectory", dspy.InputField(), type_=str)
            .append("next_thought", dspy.OutputField(), type_=str)
            .append(
                "next_tool_name",
                dspy.OutputField(),
                type_=Literal[tuple(self.tools.keys())],
            )
            .append("next_tool_args", dspy.OutputField(), type_=dict[str, Any])
        )

        return dspy.Predict(react_signature)

    def _build_fallback_module(self) -> type[Module]:
        signature = self.signature
        fallback_signature = dspy.Signature(
            {**signature.input_fields, **signature.output_fields},
            signature.instructions,
        ).append("trajectory", dspy.InputField(), type_=str)
        return dspy.ChainOfThought(fallback_signature)

    def _format_trajectory(self, trajectory: dict[str, Any]):
        adapter = dspy.settings.adapter or dspy.ChatAdapter()
        trajectory_signature = dspy.Signature(f"{', '.join(trajectory.keys())} -> x")
        return adapter.format_user_message_content(trajectory_signature, trajectory)

    def forward(self, **input_args):
        trajectory = {}
        max_iters = input_args.pop("max_iters", self.max_iters)
        for idx in range(max_iters):
            try:
                pred = self._call_with_potential_trajectory_truncation(
                    self.react, trajectory, **input_args
                )
            except ValueError as err:
                logger.warning(
                    f"Ending the trajectory: Agent failed to select a valid tool: {_fmt_exc(err)}"
                )
                break

            trajectory[f"thought_{idx}"] = pred.next_thought
            trajectory[f"tool_name_{idx}"] = pred.next_tool_name
            trajectory[f"tool_args_{idx}"] = pred.next_tool_args

            try:
                result = self.tools[pred.next_tool_name](**pred.next_tool_args)

                # This is how meta tools return multiple tools, the first argument is
                # the actual observation, the rest are new tools to add. Once we have
                # add them, we need to rebuild the react module to include them.
                # NOTE: tools will remain available for the rest of the trajectory,
                # but won't be available in the next call to the agent.
                if isinstance(result, ToolsUpgradeResponse):
                    new_tools = result.new_tools
                    observation = result.observation
                    for new_tool in new_tools:
                        if not isinstance(new_tool, Tool):
                            new_tool = Tool(new_tool)
                        self.tools[new_tool.name] = new_tool
                    self.react = self._build_react_module()
                else:
                    observation = result

                trajectory[f"observation_{idx}"] = observation
            except Exception as err:
                trajectory[
                    f"observation_{idx}"
                ] = f"Execution error in {pred.next_tool_name}: {_fmt_exc(err)}"

            if pred.next_tool_name == "finish":
                break

        extract = self._call_with_potential_trajectory_truncation(
            self.extract, trajectory, **input_args
        )
        return dspy.Prediction(trajectory=trajectory, **extract)

    async def aforward(self, **input_args):
        trajectory = {}
        max_iters = input_args.pop("max_iters", self.max_iters)
        for idx in range(max_iters):
            try:
                pred = await self._async_call_with_potential_trajectory_truncation(
                    self.react, trajectory, **input_args
                )
            except ValueError as err:
                logger.warning(
                    f"Ending the trajectory: Agent failed to select a valid tool: {_fmt_exc(err)}"
                )
                break

            trajectory[f"thought_{idx}"] = pred.next_thought
            trajectory[f"tool_name_{idx}"] = pred.next_tool_name
            trajectory[f"tool_args_{idx}"] = pred.next_tool_args

            try:
                observation = await self.tools[pred.next_tool_name](
                    **pred.next_tool_args
                )

                # This is how meta tools return multiple tools, the first argument is
                # the actual observation, the rest are new tools to add. Once we have
                # add them, we need to rebuild the react module to include them.
                # NOTE: tools will remain available for the rest of the trajectory,
                # but won't be available in the next call to the agent.
                if isinstance(observation, (list, tuple)):
                    for new_tool in observation[1:]:
                        if not isinstance(new_tool, Tool):
                            new_tool = Tool(new_tool)
                        self.tools[new_tool.name] = new_tool
                    self.react = self._build_react_module()

                    observation = observation[0]

                trajectory[f"observation_{idx}"] = observation
            except Exception as err:
                trajectory[
                    f"observation_{idx}"
                ] = f"Execution error in {pred.next_tool_name}: {_fmt_exc(err)}"

            if pred.next_tool_name == "finish":
                break

        extract = await self._async_call_with_potential_trajectory_truncation(
            self.extract, trajectory, **input_args
        )
        return dspy.Prediction(trajectory=trajectory, **extract)

    def _call_with_potential_trajectory_truncation(
        self, module, trajectory, **input_args
    ):
        for _ in range(3):
            try:
                return module(
                    **input_args,
                    trajectory=self._format_trajectory(trajectory),
                )
            except ContextWindowExceededError:
                logger.warning(
                    "Trajectory exceeded the context window, truncating the oldest tool call information."
                )
                trajectory = self.truncate_trajectory(trajectory)

    async def _async_call_with_potential_trajectory_truncation(
        self, module, trajectory, **input_args
    ):
        for _ in range(3):
            try:
                return await module.acall(
                    **input_args,
                    trajectory=self._format_trajectory(trajectory),
                )
            except ContextWindowExceededError:
                logger.warning(
                    "Trajectory exceeded the context window, truncating the oldest tool call information."
                )
                trajectory = self.truncate_trajectory(trajectory)

    def truncate_trajectory(self, trajectory):
        """Truncates the trajectory so that it fits in the context window.

        Users can override this method to implement their own truncation logic.
        """

        keys = list(trajectory.keys())
        if len(keys) < 4:
            # Every tool call has 4 keys: thought, tool_name, tool_args, and
            # observation.
            raise ValueError(
                "The trajectory is too long so your prompt exceeded the context window, but the "
                "trajectory cannot be truncated because it only has one tool call."
            )

        for key in keys[:4]:
            trajectory.pop(key)

        return trajectory
