# app/api/chat.py
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.repository import (
    create_conversation,
    insert_message,
    get_conversation_history,
    list_conversations,
    conversation_exists,
    delete_conversation
)
from app.services.query_service import QueryService

router = APIRouter(tags=["chat"])

# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class StartChatRequest(BaseModel):
    """Start a new conversation with optional first message."""
    title_preview: Optional[str] = Field(
        None,
        max_length=120,
        description="Preview title from first message"
    )
    first_message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Initial user message to start the conversation"
    )


class SendMessageRequest(BaseModel):
    """Send a message in an existing conversation."""
    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User message content"
    )


class ChatMessageResponse(BaseModel):
    """Response for a single chat message."""
    message_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    sources: List[Dict[str, Any]] = []


class StartChatResponse(BaseModel):
    """Response for starting a new conversation."""
    conversation_id: str
    title: Optional[str]
    first_message_id: str


class SendMessageResponse(BaseModel):
    """Response for sending a message."""
    conversation_id: str
    message_id: str
    role: str
    content: str
    sources: List[Dict[str, Any]] = []


class ChatHistoryResponse(BaseModel):
    """Response for conversation history."""
    conversation_id: str
    messages: List[ChatMessageResponse]


class ErrorResponse(BaseModel):
    """Generic error response."""
    error: str
    detail: Optional[str] = None


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

def get_query_service() -> QueryService:
    """Dependency to get QueryService instance."""
    return QueryService()


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post(
    "/start",
    response_model=StartChatResponse,
    responses={500: {"model": ErrorResponse}}
)
def start_chat(
    request: StartChatRequest,
    query_service: QueryService = Depends(get_query_service)
):
    """Start a new conversation with an initial user message."""
    # Create new conversation
    conv_id = create_conversation()

    # Store initial user message
    first_msg_id = insert_message(
        conversation_id=conv_id,
        role="user",
        content=request.first_message
    )

    # Generate title from first message (or use provided preview)
    title = request.title_preview or request.first_message[:100] + ("..." if len(request.first_message) > 100 else "")

    # Process with LLM (no history for first message)
    try:
        result = query_service.process_query(
            query=request.first_message,
        )
    except Exception as e:
        print(f"QueryService error in start_chat: {e}")
        # Return without assistant response if LLM fails
        return StartChatResponse(
            conversation_id=conv_id,
            title=title,
            first_message_id=first_msg_id
        )

    # Extract answer and sources from result
    answer, sources = _extract_answer_and_sources(result)

    # Normalize sources for API response
    normalized_sources = _normalize_sources(sources)

    # Store assistant response
    assistant_msg_id = insert_message(
        conversation_id=conv_id,
        role="assistant",
        content=answer,
        sources=normalized_sources
    )

    return StartChatResponse(
        conversation_id=conv_id,
        title=title,
        first_message_id=first_msg_id
    )


@router.post(
    "/{conversation_id}/message",
    response_model=SendMessageResponse,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    query_service: QueryService = Depends(get_query_service)
):
    """Send a message in an existing conversation and get assistant response."""
    # Validate conversation exists
    if not conversation_exists(conversation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found"
        )

    # Store user message
    user_msg_id = insert_message(
        conversation_id=conversation_id,
        role="user",
        content=request.content
    )

    # Get recent history for context
    history = get_conversation_history(conversation_id, limit=10)

    # Build context string from history
    context_messages = []
    for msg in history[:-1]:  # Exclude the just-added message
        context_messages.append(f"{msg['role']}: {msg['content']}")

    context = "\n".join(context_messages) if context_messages else None

    # Process with LLM
    try:
        result = query_service.process_query(
            query=request.content,
            context=context
        )
    except Exception as e:
        print(f"QueryService error in send_message: {e}")
        # Return error response
        return SendMessageResponse(
            conversation_id=conversation_id,
            message_id="error_" + user_msg_id,
            role="assistant",
            content="I apologize, but I encountered an error processing your request. Please try again.",
            sources=[]
        )

    # Extract answer and sources from result
    answer, sources = _extract_answer_and_sources(result)

    # Normalize sources for API response
    normalized_sources = _normalize_sources(sources)

    # Store assistant response
    assistant_msg_id = insert_message(
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
        sources=normalized_sources
    )

    return SendMessageResponse(
        conversation_id=conversation_id,
        message_id=assistant_msg_id,
        role="assistant",
        content=answer,
        sources=normalized_sources
    )


@router.get(
    "/{conversation_id}/history",
    response_model=ChatHistoryResponse,
    responses={404: {"model": ErrorResponse}}
)
def get_history(conversation_id: str):
    """Get message history for a conversation."""
    if not conversation_exists(conversation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found"
        )

    messages = get_conversation_history(conversation_id)
    message_responses = []
    for msg in messages:
        message_responses.append(
            ChatMessageResponse(
                message_id=msg["id"],  # FIX 1: Changed from msg["message_id"] to msg["id"]
                role=msg["role"],
                content=msg["content"],
                timestamp=msg["created_at"],
                sources=msg.get("sources", [])
            )
        )

    return ChatHistoryResponse(
        conversation_id=conversation_id,
        messages=message_responses
    )


@router.get("/conversations")
def list_all_conversations():
    """List all conversations."""
    conversations = list_conversations()
    return {"conversations": conversations}


@router.delete("/{conversation_id}")
def delete_chat(conversation_id: str):
    """Delete a conversation."""
    if not conversation_exists(conversation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found"
        )
    
    delete_conversation(conversation_id)
    return {"status": "deleted", "conversation_id": conversation_id}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _extract_answer_and_sources(result):
    """Extract answer and sources from QueryService result."""
    if isinstance(result, dict):
        # FIX 2: Prioritize retriever sources over LLM citations
        sources = result.get('sources', [])
        if sources:
            # Use retriever sources (from our RAG)
            if 'response' in result:
                response_obj = result['response']
                if hasattr(response_obj, 'answer'):
                    answer = response_obj.answer
                elif isinstance(response_obj, dict):
                    answer = response_obj.get('answer', 'I could not process your request.')
                else:
                    answer = 'I could not process your request.'
            elif 'answer' in result:
                answer = result.get('answer', 'I could not process your request.')
            else:
                answer = 'I could not process your request.'
            return answer, sources
        
        # Fall back to old behavior (LLM citations)
        if 'response' in result:
            response_obj = result['response']
            if hasattr(response_obj, 'answer'):
                answer = response_obj.answer
                sources = response_obj.citations if hasattr(response_obj, 'citations') else []
            elif isinstance(response_obj, dict):
                answer = response_obj.get('answer', 'I could not process your request.')
                sources = response_obj.get('citations', [])
            else:
                answer = 'I could not process your request.'
                sources = []
        elif 'answer' in result:
            answer = result.get('answer', 'I could not process your request.')
            sources = result.get('citations', [])
        else:
            answer = 'I could not process your request.'
            sources = []
    elif hasattr(result, 'answer'):
        answer = result.answer
        sources = result.citations if hasattr(result, 'citations') else []
    else:
        answer = str(result)
        sources = []
    
    return answer, sources


def _normalize_sources(sources):
    """Normalize sources to the API response format."""
    normalized_sources = []
    for src in sources:
        if isinstance(src, dict):
            normalized_sources.append({
                "chunk_id": src.get("chunk_id", ""),
                "document_id": src.get("document_id", ""),
                "chunk_index": src.get("chunk_index", 0),  # Changed from "page" to match our schema
                "preview": src.get("preview", "")[:200],
                "score": src.get("score", 0.0)
            })
        elif isinstance(src, str):
            normalized_sources.append({
                "chunk_id": src,
                "document_id": "",
                "chunk_index": 0,
                "preview": "",
                "score": 0.0
            })
    return normalized_sources