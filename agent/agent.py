try:
    from langchain_groq import ChatGroq
except Exception:
    ChatGroq = None
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
try:
    from .agent_tools import QueryByActorTool, QueryByActorAndWordsTool
except Exception:
    from agent_tools import QueryByActorTool, QueryByActorAndWordsTool
import os
from dotenv import load_dotenv


load_dotenv()

# Instantiate LLM only if the runtime package is available. This lets the module
# be imported or run for prompt/message generation without having the external
# `langchain_groq` dependency installed.
if ChatGroq is not None:
    llm = ChatGroq(model="qwen/qwen3.6-27b",
                   temperature=0.8,
                   api_key=os.getenv("GROQ_API_KEY2"))
    tools = [QueryByActorTool(), QueryByActorAndWordsTool()]
    try:
        llm.bind(tools)
    except Exception:
        # Binding is optional for offline runs; ignore binding errors here.
        pass
else:
    llm = None
    tools = [QueryByActorTool(), QueryByActorAndWordsTool()]


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful geopolitical analysis assistant that finds information about geopolitical events."
            "If tools require for follow up question, make sure to ask for follow up question, Make sure to include any"
            "available options that need to be clarified in the follow up questions. Do only the things user specifically"
            "requested. If a tool outputs multiple options, ask user to select one or more of them in follow up question.",
            
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ]
)
class Agent:
    """Lightweight agent wrapper exposing the LLM, bound tools and prompt.

    Use `prepare_messages` to get formatted messages for the LLM, and
    `call_llm` as a convenience wrapper that attempts common LLM methods.
    If the runtime method isn't available, `call_llm` raises with guidance.
    """

    def __init__(self, llm, tools, prompt: ChatPromptTemplate):
        self.llm = llm
        self.tools = tools
        self.prompt = prompt

    def prepare_messages(self, input_text: str, chat_history=None, agent_scratchpad=None):
        """Return prompt messages ready to pass to the LLM runtime."""
        values = {
            "input": input_text,
            "chat_history": chat_history or [],
            "agent_scratchpad": agent_scratchpad or []
        }
        return self.prompt.format_messages(**values)

    def call_llm(self, input_text: str, chat_history=None, agent_scratchpad=None, **kwargs):
        """Convenience wrapper that attempts to call common LLM methods.

        It first builds prompt messages via `prepare_messages` and then
        tries `generate` and `predict_messages` on the llm. If neither is
        available, it raises a descriptive error so the caller can handle
        the runtime-specific invocation.
        """
        messages = self.prepare_messages(input_text, chat_history, agent_scratchpad)
        # Try a couple of common method names used by LangChain-style LLMs.
        if self.llm is None:
            raise RuntimeError("LLM runtime is not available in this environment. Install the required SDK or set up the model before calling the LLM.")
        if hasattr(self.llm, "generate"):
            return self.llm.generate(messages, **kwargs)
        if hasattr(self.llm, "predict_messages"):
            return self.llm.predict_messages(messages, **kwargs)
        raise RuntimeError(
            "LLM runtime does not expose a supported call method. "
            "Use `prepare_messages()` and call your model runtime with the returned messages."
        )


agent = Agent(llm=llm, tools=tools, prompt=prompt)


if __name__ == "__main__":
    # Simple example: prepare messages for a sample question.
    msgs = agent.prepare_messages("Find events mentioning Russia and Ukraine involving military action.")
    print("Prepared messages (first two):", msgs[:2])