from fastapi import BackgroundTasks, Depends, Query, HTTPException
from supabase import Client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import uuid

from src import wire as w
from src.db import (
    get_db_session_fa,
    UserProfile,
    ContentGeneration,
    ContentType,
    Conversation,
)
from src.dependencies import get_current_user
from src.settings import get_supabase_client
from src.content.video import generate_video_content
from src.content.audio import generate_audio_content
from src.content.image import generate_image_content


# Meditation Endpoints
async def create_content(
    request: w.ContentGenerationRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_client),
) -> w.ContentGenerationResponse:
    """POST /api/meditation/create - Generate meditation content"""

    content_id = "<failed>"
    match request.mode:
        case ContentType.AUDIO.value:
            # Get the conversation to get the user_id
            query = select(Conversation).where(
                Conversation.id == request.conversation_id
            )
            result = await session.execute(query)
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation with id {request.conversation_id} not found",
                )

            # Create ContentGeneration record immediately with processing status
            content_id = str(uuid.uuid4())
            content_generation = ContentGeneration(
                id=content_id,
                user_id=conversation.user_id,
                conversation_id=request.conversation_id,
                message_id=request.message_id,
                content_type=ContentType.AUDIO,
                content_path=None,  # Will be updated when generation completes
                transcript=None,  # Will be updated when generation completes
                voice_id="shimmer",
            )

            session.add(content_generation)
            await session.commit()

            # Add audio generation to background tasks
            background_tasks.add_task(
                generate_audio_content,
                content_id,
                request.conversation_id,
                request.message_id,
            )

        case ContentType.VIDEO.value:
            # Get the conversation to get the user_id
            query = select(Conversation).where(
                Conversation.id == request.conversation_id
            )
            result = await session.execute(query)
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation with id {request.conversation_id} not found",
                )

            # Create ContentGeneration record immediately with processing status
            content_id = str(uuid.uuid4())
            content_generation = ContentGeneration(
                id=content_id,
                user_id=conversation.user_id,
                conversation_id=request.conversation_id,
                message_id=request.message_id,
                content_type=ContentType.VIDEO,
                content_path=None,  # Will be updated when generation completes
                transcript=None,  # Will be updated when generation completes
                voice_id="shimmer",
            )

            session.add(content_generation)
            await session.commit()

            # Add video generation to background tasks
            background_tasks.add_task(
                generate_video_content,
                content_id,
                request.conversation_id,
                request.message_id,
            )
        case ContentType.IMAGE.value:
            # Get the conversation to get the user_id
            query = select(Conversation).where(
                Conversation.id == request.conversation_id
            )
            result = await session.execute(query)
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation with id {request.conversation_id} not found",
                )

            # Create ContentGeneration record immediately with processing status
            content_id = str(uuid.uuid4())
            content_generation = ContentGeneration(
                id=content_id,
                user_id=conversation.user_id,
                conversation_id=request.conversation_id,
                message_id=request.message_id,
                content_type=ContentType.IMAGE,
                content_path=None,  # Will be updated when generation completes
                cc_text=None,  # Will be updated when generation completes
                cc_theme="nature_sunset",
            )

            session.add(content_generation)
            await session.commit()

            # Add image generation to background tasks
            background_tasks.add_task(
                generate_image_content,
                content_id,
                request.conversation_id,
                request.message_id,
            )
        case _:
            raise HTTPException(
                status_code=400,
                detail="Invalid content type. Must be 'audio', 'video', or 'image'",
            )
    return w.ContentGenerationResponse(id=content_id)


async def get_content(
    content_id: str,
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_client),
) -> w.ContentGeneration | w.ContentGenerationResponse:
    """GET /api/content/{id} - Get content details and download URLs. If not complete
    return a ContentGenerationResponse with status processing"""

    # Validate UUID format
    try:
        content_uuid = UUID(content_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid content ID format")

    # Query the content generation record
    query = select(ContentGeneration).where(
        ContentGeneration.id == content_uuid,
        ContentGeneration.user_id == current_user.id,
    )
    result = await session.execute(query)
    content: ContentGeneration | None = result.scalar_one_or_none()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Determine status based on content_path availability
    if content.content_path:
        # Content is complete, generate presigned URL and return full details
        try:
            # Generate presigned URL for download (expires in 1 hour)
            presigned_response = spb_client.storage.from_(
                "generations"
            ).create_signed_url(
                content.content_path, 3600  # 1 hour expiry
            )

            if presigned_response.get("error"):
                # Fallback to processing status if URL generation fails
                return w.ContentGenerationResponse(
                    id=str(content.id),
                    status="processing",
                )

            content_url = presigned_response.get("signedURL")

            return w.ContentGeneration(
                id=str(content.id),
                status="complete",
                conversation_id=str(content.conversation_id),
                message_id=str(content.message_id),
                content_type=content.content_type.value,
                content_url=content_url,
                created_at=content.created_at,
                transcript=content.transcript,
            )

        except Exception:
            # If URL generation fails, return processing status
            return w.ContentGenerationResponse(id=str(content.id), status="processing")
    else:
        # Content is still processing
        return w.ContentGenerationResponse(id=str(content.id), status="processing")
