"""Chat API endpoints with memory functionality."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.core.agent.chatNode import (
    chat_with_memory,
    get_conversation_history,
    inspect_memory,
)
from app.core.auth import get_current_user

router = APIRouter()


class ChatRequest(BaseModel):
    """Request model for chat messages."""

    message: str = Field(..., description="The user's message")
    thread_id: Optional[str] = Field(
        None,
        description="Unique thread ID for conversation continuity. If not provided, a new thread will be created.",
    )


class ChatResponse(BaseModel):
    """Response model for chat messages."""

    response: str = Field(..., description="The agent's response")
    thread_id: str = Field(..., description="The thread ID for this conversation")
    message_count: int = Field(
        ..., description="Total number of messages in this thread"
    )


class ConversationHistory(BaseModel):
    """Model for conversation history."""

    thread_id: str = Field(..., description="The thread ID")
    messages: List[dict] = Field(
        ..., description="List of messages in the conversation"
    )
    total_messages: int = Field(..., description="Total number of messages")


class MemoryState(BaseModel):
    """Model for memory state inspection."""

    thread_id: str = Field(..., description="The thread ID")
    message_count: int = Field(..., description="Number of messages in conversation")
    next_node: str = Field(..., description="Next node in the graph")
    step: int = Field(..., description="Current step in the conversation")


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    request: ChatRequest, current_user: dict = Depends(get_current_user)
):
    """
    Chat with the DocuChat agent using persistent memory.

    Each user gets their own conversation thread that persists across requests.
    """
    try:
        # Generate thread_id if not provided
        if not request.thread_id:
            thread_id = f"user_{current_user['user_id']}_{uuid.uuid4().hex[:8]}"
        else:
            thread_id = f"user_{current_user['user_id']}_{request.thread_id}"

        # Get the agent's response
        response = chat_with_memory(request.message, thread_id)

        # Get conversation history to count messages
        history = get_conversation_history(thread_id)

        return ChatResponse(
            response=response, thread_id=thread_id, message_count=len(history)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.get("/chat/{thread_id}/history", response_model=ConversationHistory)
async def get_chat_history(
    thread_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get the conversation history for a specific thread.

    The thread_id should be the one returned from a previous chat request.
    """
    try:
        # Ensure the thread belongs to the current user
        if not thread_id.startswith(f"user_{current_user['user_id']}_"):
            raise HTTPException(status_code=403, detail="Access denied to this thread")

        # Get conversation history
        history = get_conversation_history(thread_id)

        # Convert messages to dict format for JSON serialization
        messages = []
        for msg in history:
            messages.append(
                {
                    "content": msg.content if hasattr(msg, "content") else str(msg),
                    "type": msg.__class__.__name__,
                    "id": getattr(msg, "id", None),
                }
            )

        return ConversationHistory(
            thread_id=thread_id, messages=messages, total_messages=len(messages)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.get("/chat/{thread_id}/memory", response_model=MemoryState)
async def inspect_chat_memory(
    thread_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Inspect the memory state for a specific conversation thread.

    This provides debugging information about the conversation state.
    """
    try:
        # Ensure the thread belongs to the current user
        if not thread_id.startswith(f"user_{current_user['user_id']}_"):
            raise HTTPException(status_code=403, detail="Access denied to this thread")

        # Get memory state
        snapshot = inspect_memory(thread_id)

        return MemoryState(
            thread_id=thread_id,
            message_count=len(snapshot.values["messages"]),
            next_node=str(snapshot.next) if snapshot.next else "END",
            step=snapshot.metadata.get("step", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to inspect memory: {str(e)}"
        )


@router.post("/chat/new-thread")
async def create_new_thread(current_user: dict = Depends(get_current_user)):
    """
    Create a new conversation thread.

    Returns a new thread_id that can be used for subsequent chat requests.
    """
    try:
        thread_id = f"user_{current_user['user_id']}_{uuid.uuid4().hex[:8]}"

        return {"thread_id": thread_id, "message": "New conversation thread created"}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create thread: {str(e)}"
        )


@router.get("/chat/threads")
async def list_user_threads(current_user: dict = Depends(get_current_user)):
    """
    List all conversation threads for the current user.

    Note: This is a basic implementation. In production, you might want to
    store thread metadata in a database for better management.
    """
    try:
        # This is a placeholder implementation
        # In a real application, you'd query a database for user threads
        return {"threads": [], "message": "Thread listing not fully implemented yet"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list threads: {str(e)}")
