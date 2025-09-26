"""Agent service for managing LangGraph agent with proper user namespacing and configuration."""

import asyncio
from typing import Dict, List, Any, Optional
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import InMemorySaver
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.graph.message import add_messages

from app.core.config import get_settings
from app.services.external_apis.pinecone_service import PineconeService
from app.utils.logging import configure_logging

logger = configure_logging()


class State(TypedDict):
    """Agent state definition."""

    messages: Annotated[list, add_messages]


class AgentService:
    """Service for managing LangGraph agent with user context and proper namespacing."""

    def __init__(self):
        """Initialize the agent service."""
        self.settings = get_settings()
        self.pinecone_service = PineconeService()
        self._graph = None
        self._checkpointer = None
        self._tools = None
        self._llm = None

    def _get_checkpointer(self):
        """Get or create the appropriate checkpointer based on configuration."""
        if self._checkpointer is not None:
            return self._checkpointer

        backend = self.settings.agent_memory_backend.lower()

        if backend == "redis":
            # TODO: Implement Redis checkpointer when langgraph supports it
            logger.warning(
                "Redis checkpointer not available in current LangGraph version, falling back to memory"
            )
            self._checkpointer = InMemorySaver()
        elif backend == "postgres":
            # TODO: Implement Postgres checkpointer when langgraph supports it
            logger.warning(
                "Postgres checkpointer not available in current LangGraph version, falling back to memory"
            )
            self._checkpointer = InMemorySaver()
        else:
            self._checkpointer = InMemorySaver()

        return self._checkpointer

    def _get_llm(self):
        """Get or create the LLM instance."""
        if self._llm is not None:
            return self._llm

        if not self.settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is required for agent service")

        self._llm = init_chat_model(
            model=self.settings.agent_model,
            model_provider=self.settings.agent_model_provider,
            base_url=self.settings.agent_base_url,
            api_key=self.settings.openrouter_api_key,
        )
        return self._llm

    def _get_tools(self, user_email: str):
        """Get tools configured for a specific user."""
        if self._tools is not None:
            return self._tools

        @tool
        def search_documents(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
            """Search across all user documents for information related to the query."""
            try:
                results = asyncio.run(
                    self.pinecone_service.search_across_documents(
                        user_email=user_email, query=query, top_k=max_results
                    )
                )
                return results
            except Exception as e:
                logger.error(f"Search failed for user {user_email}: {e}")
                return [{"error": f"Search failed: {str(e)}"}]

        @tool
        def search_in_specific_file(
            filename: str, query: str, max_results: int = 5
        ) -> List[Dict[str, Any]]:
            """Search for information within a specific file."""
            try:
                results = asyncio.run(
                    self.pinecone_service.search_in_file(
                        user_email=user_email,
                        filename=filename,
                        query=query,
                        top_k=max_results,
                    )
                )
                return results
            except Exception as e:
                logger.error(f"File search failed for user {user_email}: {e}")
                return [{"error": f"File search failed: {str(e)}"}]

        @tool
        def get_document_context(
            filename: str, max_chunks: int = 20
        ) -> List[Dict[str, Any]]:
            """Get comprehensive context from a specific document file."""
            try:
                results = asyncio.run(
                    self.pinecone_service.get_file_context(
                        user_email=user_email, filename=filename, max_chunks=max_chunks
                    )
                )
                return results
            except Exception as e:
                logger.error(f"Context retrieval failed for user {user_email}: {e}")
                return [{"error": f"Context retrieval failed: {str(e)}"}]

        @tool
        def get_file_summary(filename: str) -> Dict[str, Any]:
            """Get summary information about a specific document."""
            try:
                result = asyncio.run(
                    self.pinecone_service.get_document_summary(
                        user_email=user_email, filename=filename
                    )
                )
                return result
            except Exception as e:
                logger.error(f"Summary retrieval failed for user {user_email}: {e}")
                return {"error": f"Summary retrieval failed: {str(e)}"}

        self._tools = [
            search_documents,
            search_in_specific_file,
            get_document_context,
            get_file_summary,
        ]
        return self._tools

    def _get_graph(self, user_email: str):
        """Get or create the agent graph for a specific user."""
        if self._graph is not None:
            return self._graph

        # Create graph builder
        graph_builder = StateGraph(State)

        # Get LLM and tools
        llm = self._get_llm()
        tools = self._get_tools(user_email)
        llm_with_tools = llm.bind_tools(tools)

        def chatbot(state: State):
            return {"messages": [llm_with_tools.invoke(state["messages"])]}

        # Create tool node
        tool_node = ToolNode(tools=tools)

        # Add nodes to the graph
        graph_builder.add_node("chatbot", chatbot)
        graph_builder.add_node("tools", tool_node)

        # Set up edges
        graph_builder.add_edge(START, "chatbot")
        graph_builder.add_conditional_edges(
            "chatbot",
            tools_condition,
        )
        graph_builder.add_edge("tools", "chatbot")

        # Compile the graph with checkpointer
        self._graph = graph_builder.compile(checkpointer=self._get_checkpointer())
        return self._graph

    def chat_with_memory(
        self, user_input: str, user_email: str, thread_id: str = "default"
    ) -> str:
        """
        Chat with the agent using memory for a specific user.

        Args:
            user_input: The user's message
            user_email: The user's email for namespace isolation
            thread_id: Unique identifier for the conversation thread

        Returns:
            The agent's response as a string
        """
        try:
            graph = self._get_graph(user_email)
            config = {"configurable": {"thread_id": thread_id}}

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
            logger.error(f"Error in chat_with_memory for user {user_email}: {e}")
            return "I apologize, but I encountered an error processing your request. Please try again."

    def get_conversation_history(
        self, user_email: str, thread_id: str = "default"
    ) -> list:
        """
        Get the conversation history for a specific thread and user.

        Args:
            user_email: The user's email for namespace isolation
            thread_id: Unique identifier for the conversation thread

        Returns:
            List of messages in the conversation
        """
        try:
            graph = self._get_graph(user_email)
            config = {"configurable": {"thread_id": thread_id}}
            snapshot = graph.get_state(config)
            return snapshot.values["messages"]
        except Exception as e:
            logger.error(
                f"Error in get_conversation_history for user {user_email}: {e}"
            )
            return []

    def inspect_memory(
        self, user_email: str, thread_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Inspect the current state of the conversation for a specific user.

        Args:
            user_email: The user's email for namespace isolation
            thread_id: Unique identifier for the conversation thread

        Returns:
            Dictionary containing memory state information
        """
        try:
            graph = self._get_graph(user_email)
            config = {"configurable": {"thread_id": thread_id}}
            snapshot = graph.get_state(config)

            return {
                "thread_id": thread_id,
                "user_email": user_email,
                "message_count": len(snapshot.values["messages"]),
                "next_node": str(snapshot.next) if snapshot.next else "END",
                "step": snapshot.metadata.get("step", 0),
            }
        except Exception as e:
            logger.error(f"Error in inspect_memory for user {user_email}: {e}")
            return {
                "thread_id": thread_id,
                "user_email": user_email,
                "message_count": 0,
                "next_node": "ERROR",
                "step": 0,
                "error": str(e),
            }

    def stream_graph_updates(
        self, user_input: str, user_email: str, thread_id: str = "default"
    ):
        """Stream graph updates with memory persistence using thread_id for a specific user."""
        try:
            graph = self._get_graph(user_email)
            config = {"configurable": {"thread_id": thread_id}}

            for event in graph.stream(
                {"messages": [HumanMessage(content=user_input)]},
                config,
                stream_mode="values",
            ):
                if hasattr(event["messages"][-1], "content"):
                    print("Assistant:", event["messages"][-1].content)
                else:
                    print("Assistant:", str(event["messages"][-1]))
        except Exception as e:
            logger.error(f"Error in stream_graph_updates for user {user_email}: {e}")
            print(f"Error: {e}")


# Global agent service instance
_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """Get or create the global agent service instance."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
