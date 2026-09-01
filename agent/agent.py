from langchain_groq import ChatGroq
# from langchain_nvidia_ai_endpoints import ChatNVIDIA
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
from typing import List
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage, BaseMessage
import os
from dotenv import load_dotenv

load_dotenv()

os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_PROJECT"] = "Argus"


llm = ChatGroq(model="openai/gpt-oss-120b",
                api_key=os.getenv("GROQ_API_KEY2"),
                temperature=0.0)



prompt = ChatPromptTemplate.from_messages([
    ("system", (
        """ 
        You are a helpful Geopolitical analyst, answer the questions the user asks.
        Do multi-step reasoning for answering questions the user asked. Do not call same tool twice with same arguments.
        If you have all the information for answering question, then call 'final_answer' tool after forming a final answer.
        The final answer should be formed only from the context retrieved using tools. If you can't answer a question of user just
        say 'I dont know'. 
        """
    )),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])

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


class CustomAutonomousAgent:
    """A custom autonomous agent that handles ReAct loop."""

    chat_history: List[BaseMessage]

    def __init__(self, max_iter: int = 10):
        self.chat_history = []
        self.max_iter = max_iter

        self.tools = [QueryByActorTool(), 
                      QueryByActorAndWordsTool(), 
                      QueryByLocationandWordsTool(), 
                      QueryByEventwordsTool(), 
                      QueryByLocationTool(),
                      QueryRelatedEventsTool(),
                      QueryRelatedEventswithWordsTool(), 
                      final_answer]
        self.name2tool = {tool.name: tool.invoke for tool in self.tools}

        self.agent: RunnableSerializable = (
            {
                "input": lambda x: x["input"],
                "chat_history": lambda x: x["chat_history"],
                "agent_scratchpad": lambda x: x.get("agent_scratchpad", [])
            }
            | prompt
            | llm.bind_tools(self.tools, tool_choice="auto")
        )

    def invoke(self, input:str) -> dict:
        """Execute the agent loop"""
        count = 0
        agent_scratchpad = []
        tools_used = []

        while count < self.max_iter:
            print(f"agent_scratchpad: {agent_scratchpad} \n\n")

            try:
                agent_resp = self.agent.invoke({
                    "input": input,
                    "chat_history": self.chat_history,
                    "agent_scratchpad": agent_scratchpad
                })

            except BadRequestError as e:
                recovered = _recover_from_tool_use_failure(e)
                if recovered and "answer" in recovered:
                    print("Recovered from malformed/truncated tool call.")
                    final_answer_text = recovered["answer"]
                    self.chat_history.extend([
                        HumanMessage(content=input),
                        AIMessage(content=final_answer_text)
                    ])
                    return {"answer": final_answer_text, "tools_used": tools_used, "recovered_from_erro": True}
                raise

            if len(agent_resp.tool_calls) > 0:
                agent_scratchpad.append(agent_resp)
                tool_name = agent_resp.tool_calls[0]["name"]
                tool_args = agent_resp.tool_calls[0]["args"]
                tool_call_id = agent_resp.tool_calls[0]["id"]

                if tool_name != "final_answer":
                    tools_used.append(tool_name)

                tool_out = self.name2tool[tool_name](tool_args)

                tool_exec = ToolMessage(
                    content = f"{tool_out}", tool_call_id=tool_call_id
                )

                agent_scratchpad.append(tool_exec)

                # print(f"{count}: {tool_name}({tool_args}) -> {tool_out}")

                count += 1

                if tool_name == "final_answer":
                    final_answer_text = tool_out["answer"] if isinstance(tool_out, dict) else str(tool_out)
                # print(final_answer_text)
                    self.chat_history.extend([
                        HumanMessage(content=input),
                        AIMessage(content=str(final_answer_text))
                    ])
                    return tool_out

            else:
                final_answer_text = agent_resp.content or agent_resp.additional_kwargs.get("reasoning_content", "")  
                self.chat_history.extend([
                    HumanMessage(content=input),
                    AIMessage(content=final_answer_text)
                ])
                return {"answer": final_answer_text}
        return {"answer": "Reached max iterations wihtout final answer."}


autonomous_agent = CustomAutonomousAgent()

agent_input = "Hey, there tell me about yourself!"

while agent_input != "quit" or "exit":
    result = autonomous_agent.invoke(agent_input)
    print(result)
    agent_input = str(input("Ask me about recent geopolitical events : "))
        


# if __name__ == "__main__":
#     for t in tools:
#         print(repr(t.name), "→ valid:", t.name.replace("_", "").replace("-", "").isalnum())
#     message_input = ""
#     config = {"configurable": {"thread_id": "session_1"}}
#     while message_input != "quit":
#         message_input = input(str("Ask question what is the situation of war between Iran and US or type 'quit' to exit from loop : "))
#         try:
#             for event in agent.stream(config=config, input={"messages": [{"role": "user", "content": message_input}]}):
#                 if "model" in event:
#                     messages = event["model"]["messages"]
#                     for msg in messages:
#                         if hasattr(msg, "additional_kwargs") and "reasoning_content" in msg.additional_kwargs:
#                             reasoning = msg.additional_kwargs["reasoning_content"]
#                             if reasoning:
#                                 print(f"\n🤔 [Thinking]: {reasoning}\n")
                        
#                         if hasattr(msg, "content") and len(msg.content) > 1:
#                             print(f"\n[AI] : {msg.content} ")

#                         if msg.tool_calls:
#                             for tool in msg.tool_calls:
#                                 print(f"🔍 [Tool Call]: Running '{tool['name']}' with query: {tool['args'].get('query')}")

#                 elif "tools" in event:
#                     messages = event["tools"]["messages"]
#                     for msg in messages:
#                         print(f"✅ [Tool Complete]: Retrieved context from database.")
#                         print(f"📄 [Context Sample]: {msg.content[:200]}...")

#                 elif "assistant" in event or "agent" in event:
#                     node_name = "assistant" if "assistant" in event else "agent"
#                     messages = event[node_name]["messages"]
#                     for msg in messages:
#                         if msg.content:
#                             print(f"\n🤖 [Assistant]: {msg.content}")
#         except Exception as e:
#             print(f"Exception occured : {e}")

