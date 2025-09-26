import os
import asyncio
from typing import Dict, List, Any
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

from app.core.agent.stateGraph import graph_builder, State
from langgraph.graph import START
from app.services.external_apis.pinecone_service import PineconeService
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()

# Initialize Pinecone service
pinecone_service = PineconeService()

# For now, we'll use a placeholder user email - this should be made dynamic later
DEFAULT_USER_EMAIL = "avi@enclave.live"


# Custom Pinecone Tools
@tool
def search_documents(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search across all user documents for information related to the query.

    Args:
        query: The search query to find relevant information
        max_results: Maximum number of results to return (default: 10)

    Returns:
        List of relevant document chunks with metadata
    """
    try:
        results = asyncio.run(
            pinecone_service.search_across_documents(
                user_email=DEFAULT_USER_EMAIL, query=query, top_k=max_results
            )
        )
        return results
    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]


@tool
def search_in_specific_file(
    filename: str, query: str, max_results: int = 5
) -> List[Dict[str, Any]]:
    """Search for information within a specific file.

    Args:
        filename: The name of the file to search in
        query: The search query
        max_results: Maximum number of results to return (default: 5)

    Returns:
        List of relevant chunks from the specified file
    """
    try:
        results = asyncio.run(
            pinecone_service.search_in_file(
                user_email=DEFAULT_USER_EMAIL,
                filename=filename,
                query=query,
                top_k=max_results,
            )
        )
        return results
    except Exception as e:
        return [{"error": f"File search failed: {str(e)}"}]


@tool
def get_document_context(filename: str, max_chunks: int = 20) -> List[Dict[str, Any]]:
    """Get comprehensive context from a specific document file.

    Args:
        filename: The name of the file to get context from
        max_chunks: Maximum number of chunks to return (default: 20)

    Returns:
        List of document chunks in order
    """
    try:
        results = asyncio.run(
            pinecone_service.get_file_context(
                user_email=DEFAULT_USER_EMAIL, filename=filename, max_chunks=max_chunks
            )
        )
        return results
    except Exception as e:
        return [{"error": f"Context retrieval failed: {str(e)}"}]


@tool
def get_file_summary(filename: str) -> Dict[str, Any]:
    """Get summary information about a specific document.

    Args:
        filename: The name of the file to get summary for

    Returns:
        Dictionary containing file summary information
    """
    try:
        result = asyncio.run(
            pinecone_service.get_document_summary(
                user_email=DEFAULT_USER_EMAIL, filename=filename
            )
        )
        return result
    except Exception as e:
        return {"error": f"Summary retrieval failed: {str(e)}"}


# List of all tools
tools = [
    search_documents,
    search_in_specific_file,
    get_document_context,
    get_file_summary,
]


# Configure for OpenRouter
llm = init_chat_model(
    model="x-ai/grok-4-fast:free",
    model_provider="openai",  # Use openai provider for OpenRouter compatibility
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

# Bind tools to the LLM
llm_with_tools = llm.bind_tools(tools)


def chatbot(state: State):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}


# Create tool node for executing tools
tool_node = ToolNode(tools=tools)

# Add nodes to the graph
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", tool_node)

# Set up edges
graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,  # This automatically routes to "tools" if tool calls are needed
)
# After tools are executed, return to chatbot to continue conversation
graph_builder.add_edge("tools", "chatbot")


# Create memory checkpointer
memory = InMemorySaver()

# Compile the graph with memory checkpointer
graph = graph_builder.compile(checkpointer=memory)


def stream_graph_updates(user_input: str, thread_id: str = "default"):
    """Stream graph updates with memory persistence using thread_id"""
    config = {"configurable": {"thread_id": thread_id}}

    for event in graph.stream(
        {"messages": [HumanMessage(content=user_input)]}, config, stream_mode="values"
    ):
        if hasattr(event["messages"][-1], "content"):
            print("Assistant:", event["messages"][-1].content)
        else:
            print("Assistant:", str(event["messages"][-1]))


def inspect_memory(thread_id: str = "default"):
    """Inspect the current state of the conversation"""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    print(f"\n📊 Memory State for thread '{thread_id}':")
    print(f"Number of messages: {len(snapshot.values['messages'])}")
    print(f"Next node: {snapshot.next}")
    print(f"Step: {snapshot.metadata.get('step', 'N/A')}")
    return snapshot


def main():
    """Main function to run the chatbot with memory"""
    print("🤖 DocuChat Agent with Memory")
    print("=" * 50)
    print("This chatbot now has memory! It will remember our conversation.")
    print("Commands: 'quit', 'exit', 'q' to exit")
    print("Special commands: 'memory' to inspect conversation state")
    print("Try asking about your name or previous topics!")
    print("=" * 50)

    # Use a consistent thread_id for this session
    thread_id = "user_session_1"

    while True:
        try:
            user_input = input("\nUser: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            elif user_input.lower() == "memory":
                inspect_memory(thread_id)
            else:
                stream_graph_updates(user_input, thread_id)
        except (EOFError, KeyboardInterrupt):
            # fallback if input() is not available
            user_input = "What do you know about LangGraph?"
            print("User: " + user_input)
            stream_graph_updates(user_input, thread_id)
            break


def chat_with_memory(user_input: str, thread_id: str = "default") -> str:
    """
    API function to chat with the agent using memory.

    Args:
        user_input: The user's message
        thread_id: Unique identifier for the conversation thread

    Returns:
        The agent's response as a string
    """
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Get the response from the graph
        response = graph.invoke(
            {"messages": [HumanMessage(content=user_input)]}, config
        )

        # Extract the last message content
        last_message = response["messages"][-1]
        if hasattr(last_message, "content"):
            return last_message.content
        else:
            return str(last_message)
    except Exception as e:
        # Log the error and return a user-friendly message
        print(f"Error in chat_with_memory: {e}")
        return "I apologize, but I encountered an error processing your request. Please try again."


def get_conversation_history(thread_id: str = "default") -> list:
    """
    Get the conversation history for a specific thread.

    Args:
        thread_id: Unique identifier for the conversation thread

    Returns:
        List of messages in the conversation
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = graph.get_state(config)
        return snapshot.values["messages"]
    except Exception as e:
        print(f"Error in get_conversation_history: {e}")
        return []


if __name__ == "__main__":
    main()
