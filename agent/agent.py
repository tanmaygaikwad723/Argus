from langchain_groq import ChatGroq
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from agent.agent_tools import QueryByActorAndWordsTool, QueryByActorTool
from langgraph.checkpoint.memory import InMemorySaver
import os
from dotenv import load_dotenv


load_dotenv()

llm = ChatGroq(model="qwen/qwen3.6-27b",
                temperature=0.9,
                api_key=os.getenv("GROQ_API_KEY2"))
tools = [QueryByActorTool(), QueryByActorAndWordsTool()]


prompt = "You are a helpful geopolitical analysis assistant that finds information about geopolitical events. \
         Analyze the question asked by user, then extract the input words that are required to run tools based on the question. \
         If tools require for follow up question, make sure to ask for follow up question, Make sure to include any \
         available options that need to be clarified in the follow up questions. Do only the things user specifically \
         requested. If a tool outputs multiple options, ask user to select one or more of them in follow up question."
            
agent = create_agent(model=llm, tools=tools, system_prompt=prompt, checkpointer=InMemorySaver())



if __name__ == "__main__":
    for t in tools:
        print(repr(t.name), "→ valid:", t.name.replace("_", "").replace("-", "").isalnum())
    message_input = ""
    config = {"configurable": {"thread_id": "session_1"}}
    while message_input != "quit":
        message_input = input(str("Ask question what is the situation of war between Iran and US or type 'quit' to exit from loop : "))
        try:
            for event in agent.stream(config=config, input={"messages": [{"role": "user", "content": message_input}]}):
                if "model" in event:
                    messages = event["model"]["messages"]
                    for msg in messages:
                        if hasattr(msg, "additional_kwargs") and "reasoning_content" in msg.additional_kwargs:
                            reasoning = msg.additional_kwargs["reasoning_content"]
                            if reasoning:
                                print(f"\n🤔 [Thinking]: {reasoning}\n")
                        
                        if hasattr(msg, "content") and len(msg.content) > 1:
                            print(f"\n[AI] : {msg.content} ")

                        if msg.tool_calls:
                            for tool in msg.tool_calls:
                                print(f"🔍 [Tool Call]: Running '{tool['name']}' with query: {tool['args'].get('query')}")

                elif "tools" in event:
                    messages = event["tools"]["messages"]
                    for msg in messages:
                        print(f"✅ [Tool Complete]: Retrieved context from database.")
                        print(f"📄 [Context Sample]: {msg.content[:200]}...")

                elif "assistant" in event or "agent" in event:
                    node_name = "assistant" if "assistant" in event else "agent"
                    messages = event[node_name]["messages"]
                    for msg in messages:
                        if msg.content:
                            print(f"\n🤖 [Assistant]: {msg.content}")
        except Exception as e:
            print(f"Exception occured : {e}")

