from langchain.agents import create_agent
from json_repair import repair_json
import json
from groq import BadRequestError
from agent.agent_tools import (QueryByActorAndWordsTool, 
                               QueryByActorTool, 
                               QueryByLocationandWordsTool,
                               QueryByEventwordsTool,
                               QueryByLocationTool,
                               QueryRelatedEventsTool,
                               QueryRelatedEventswithWordsTool)
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.base import RunnableSerializable
from typing import Any, Iterator, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain.agents.middleware.model_retry import ModelRetryMiddleware
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage, BaseMessage
import os
from dotenv import load_dotenv

load_dotenv()

os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_PROJECT"] = "Argus"


prompt = """ 
        You are a helpful Geopolitical analyst, answer the questions the user asks.
        Do multi-step reasoning for answering questions the user asked. Do not call same tool twice with same arguments.
        If you have all the information for answering question, then call 'final_answer' tool after forming a final answer.
        The final answer should be formed only from the context retrieved using tools. If you can't answer a question of user just
        say 'I dont know'. 
        """

@tool
def final_answer(answer:str, tools_used:List[str]) -> str:
    """ 
    Use this tool to provide a final answer to the user.
    The answer should be in natural language as this will be provided
    to the user directly. The tools_used must include a list of tool
    names that were used within the 'scratchpad'.
    """
    return {"answer": answer, "tool_used": tools_used}


def _recover_from_tool_use_failure(error: BadRequestError) -> dict | None:
    """ 
    Genralized recovery for any Groq  tool_use_failed error -
    covers wrong-tool-name, malformed JSON, and truncated JSON cases
    """
    try:
        body = error.body if hasattr(error, "body") else json.loads(error.response.text)
        if body.get("error", {}).get("code") != "tool_use_failed":
            return None

        failed_gen = body["error"].get("failed_generation", "")
        if not failed_gen:
            return None

        repaired = repair_json(failed_gen)
        parsed = json.loads(repaired)

        return parsed.get("arguments", parsed)
    except Exception as inner_e:
        print(f"Recovery attempt also failed: {inner_e}")
        return None


class FinalAnswer(BaseModel):
    """The agent's final answer to the user's geopolitical question."""
    answer: str = Field(description="The natural-language answer, based only on retrieved context.")


def create_autonomous_agent():
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="nvidia/nemotron-3-ultra-550b-a55b:free",
                     api_key=os.environ.get("OPENROUTER_API_KEY"),
                     openai_api_base="https://openrouter.ai/api/v1",
                     temperature=0.0)

    return create_agent(
        model = llm,
        tools = [
            QueryByActorAndWordsTool(),
            QueryByActorTool(),
            QueryByEventwordsTool(),
            QueryByLocationandWordsTool(),
            QueryByLocationTool(),
            QueryRelatedEventsTool(),
            QueryRelatedEventswithWordsTool(),
            final_answer
        ],
        system_prompt = prompt,
        middleware = [
            ModelRetryMiddleware(
                max_retries = 3,
                retry_on = (BadRequestError,),
                on_failure = "continue"
            )
        ],
        checkpointer = InMemorySaver()
    )


def _message_content(message: BaseMessage) -> str:
    """Return displayable text from a LangChain message content value."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _tool_result_content(message: ToolMessage) -> Any:
    """Decode structured tool output while preserving non-JSON results."""
    content = message.content
    if isinstance(content, (dict, list)):
        return content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content
    return str(content)


def stream_agent_response(
    agent: Any,
    message_input: str,
    config: dict,
) -> Iterator[dict[str, Any]]:
    """Yield structured intermediate steps and the final answer from an agent run."""
    for update in agent.stream(
        config=config,
        input={"messages": [{"role": "user", "content": message_input}]},
        stream_mode="updates",
    ):
        for node_name, node_update in update.items():
            messages = node_update.get("messages", [])
            if not messages:
                yield {"type": "update", "node": node_name, "data": node_update}
                continue

            for message in messages:
                if isinstance(message, AIMessage) and message.tool_calls:
                    for tool_call in message.tool_calls:
                        yield {
                            "type": "tool_call",
                            "node": node_name,
                            "name": tool_call["name"],
                            "args": tool_call.get("args", {}),
                        }
                elif isinstance(message, ToolMessage):
                    result = _tool_result_content(message)
                    if message.name == "final_answer":
                        answer = result.get("answer", result) if isinstance(result, dict) else result
                        yield {
                            "type": "final",
                            "node": node_name,
                            "answer": answer,
                            "tool_used": result.get("tool_used", []) if isinstance(result, dict) else [],
                        }
                    else:
                        yield {
                            "type": "tool_result",
                            "node": node_name,
                            "name": message.name or message.tool_call_id,
                            "result": result,
                        }
                elif isinstance(message, AIMessage) and message.content:
                    yield {
                        "type": "assistant",
                        "node": node_name,
                        "content": _message_content(message),
                    }


def _print_stream_event(event: dict[str, Any]) -> None:
    """Render one streamed event for the command-line client."""
    event_type = event["type"]
    if event_type == "tool_call":
        print(f"\n[step] Calling {event['name']} with {event['args']}")
    elif event_type == "tool_result":
        result = event["result"]
        print(f"[step] {event['name']} returned {len(result)} result(s)" if isinstance(result, list) else f"[step] {event['name']} returned")
    elif event_type == "assistant":
        print(f"\n{event['content']}")
    elif event_type == "final":
        print(f"\nAnswer:\n{event['answer']}")


if __name__ == "__main__":
    agent = create_autonomous_agent()
    config = {"configurable": {"thread_id": "session_1"}}
    while True:
        message_input = input(
            "Ask a question, or type 'quit' or 'exit' to stop: "
        ).strip()
        if message_input.lower() in {"quit", "exit"}:
            break
        if not message_input:
            continue

        try:
            for event in stream_agent_response(agent, message_input, config):
                _print_stream_event(event)
        except KeyboardInterrupt:
            print("\nRequest cancelled.")
        except Exception as error:
            print(f"\nAgent run failed: {error}")


