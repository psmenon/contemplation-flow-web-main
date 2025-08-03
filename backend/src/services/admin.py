from tuneapi import tu

from fastapi import Depends, Query, HTTPException
from uuid import UUID
from supabase import Client
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession


from src.db import (
    get_db_session_fa,
    UserProfile as DBUserProfile,
    SourceDocument as DBSourceDocument,
    ContentGeneration,
    Message,
    Conversation,
    ContentType,
)
from src import wire as w
from src.dependencies import get_current_user
from src.settings import get_supabase_client

# ============================================================================
# 1. USER MANAGEMENT
# ============================================================================


async def list_users(
    limit: int = Query(50, le=100),
    search_term: str | None = Query(None),
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.ListUsersResponse:
    """GET /api/admin/users - List all users with filtering

    search_term will do search on name, phone"""

    # Build the base query
    query = select(DBUserProfile)

    # Apply filters: Search in name and phone_number
    if search_term:
        search_filter = or_(
            DBUserProfile.name.ilike(f"%{search_term}%"),
            DBUserProfile.phone_number.ilike(f"%{search_term}%"),
        )
        query = query.where(search_filter)

    # Apply limit and order by creation date (newest first)
    query = query.order_by(DBUserProfile.created_at.desc()).limit(limit)

    # Execute query
    result = await session.execute(query)
    db_users: list[DBUserProfile] = result.scalars().all()

    # create wire users
    wire_users = []

    # create usage stats
    for user in db_users:
        wire_user = await user.to_bm()
        conversations = await session.execute(
            select(Conversation).where(Conversation.user_id == user.id)
        )
        conversations = conversations.scalars().all()
        content_generations = await session.execute(
            select(ContentGeneration).where(ContentGeneration.user_id == user.id)
        )
        content_generations = content_generations.scalars().all()
        wire_users.append(
            w.UserWithUsage(
                id=wire_user.id,
                created_at=wire_user.created_at,
                last_active=wire_user.last_active,
                phone_number=wire_user.phone_number,
                phone_verified=wire_user.phone_verified,
                name=wire_user.name,
                role=wire_user.role,
                usage_stats={
                    "conversations": len(conversations),
                    "content_generations": {
                        "total": len(content_generations),
                        "video": len(
                            [
                                content_generation
                                for content_generation in content_generations
                                if content_generation.content_type == ContentType.VIDEO
                            ]
                        ),
                        "audio": len(
                            [
                                content_generation
                                for content_generation in content_generations
                                if content_generation.content_type == ContentType.AUDIO
                            ]
                        ),
                        "image": len(
                            [
                                content_generation
                                for content_generation in content_generations
                                if content_generation.content_type == ContentType.IMAGE
                            ]
                        ),
                    },
                },
            )
        )
    return w.ListUsersResponse(users=wire_users)


async def delete_user(
    user_id: str,
    current_user: DBUserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_client),
) -> w.SuccessResponse:
    """DELETE /api/admin/users/{id} - Delete user and all data"""

    # Validate UUID format
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Check if user exists
    query = select(DBUserProfile).where(DBUserProfile.id == user_uuid)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    # Log the deletion for audit purposes
    tu.logger.info(
        f"Admin {current_user.id} deleting user {user.id} ({user.phone_number})"
    )

    # delete content generations
    content_generations = await session.execute(
        select(ContentGeneration).where(ContentGeneration.user_id == user.id)
    )
    content_generations = content_generations.scalars().all()
    if content_generations:
        for content_generation in content_generations:
            if content_generation.content_path:
                spb_client.storage.from_("generations").remove(
                    [content_generation.content_path]
                )
                tu.logger.info(
                    f"Deleted file from storage: {content_generation.content_path}"
                )
            await session.delete(content_generation)
    await session.delete(user)  # Delete the user (cascading will handle related data)

    tu.logger.info(f"Successfully deleted user {user.id} and all associated data")
    return w.SuccessResponse(
        success=True,
        message=f"User {user.phone_number} and all associated data deleted successfully",
    )


# ============================================================================
# 2. CONTENT GENERATION
# ============================================================================


async def delete_content(
    content_id: str,
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_client),
) -> w.SuccessResponse:
    """DELETE /api/admin/content/{type}/{id} - Remove generated content"""

    # Validate UUID format
    try:
        content_uuid = UUID(content_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid content ID format")

    # Find the content generation record
    query = select(ContentGeneration).where(ContentGeneration.id == content_uuid)
    result = await session.execute(query)
    content: ContentGeneration | None = result.scalar_one_or_none()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Log the deletion for audit purposes
    tu.logger.info(f"Deleting {content.content_type} content {content.id}")

    # TODO: Delete associated files from Supabase storage
    if content.content_path:
        try:
            # Delete from Supabase storage
            spb_client.storage.from_("generations").remove([content.content_path])
            tu.logger.info(f"Deleted file from storage: {content.content_path}")
        except Exception as e:
            tu.logger.warning(f"Failed to delete file from storage: {e}")

    # Delete the content generation record
    await session.delete(content)
    # Note: session.commit() is handled automatically by the session dependency

    tu.logger.info(f"Successfully deleted {content.content_type} content {content.id}")

    return w.SuccessResponse(
        success=True,
        message=f"{content.id} {content.content_type.value} content deleted successfully",
    )


# ============================================================================
# 3. FEEDBACK
# ============================================================================


async def get_feedback(
    limit: int = Query(50, le=100),
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.AdminFeedbackResponse:
    """GET /api/admin/feedback - Get user feedback"""

    # Build query to get all messages with feedback, joining through conversations
    query = (
        select(Message, DBUserProfile)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(DBUserProfile, Conversation.user_id == DBUserProfile.id)
        .where(Message.feedback_type.is_not(None))
        .order_by(Message.feedback_given_at.desc())
        .limit(limit)
    )

    # Execute the query
    result = await session.execute(query)
    feedback_data: list[tuple[Message, DBUserProfile]] = result.all()

    # Convert to UserFeedback objects
    feedback_list = []
    for message, user in feedback_data:
        user_feedback = w.UserFeedback(
            user_id=str(user.id),
            message_id=str(message.id),
            type=message.feedback_type.value,
            comment=message.feedback_comment,
            created_at=message.feedback_given_at,
        )
        feedback_list.append(user_feedback)

    return w.AdminFeedbackResponse(feedback=feedback_list)


# ============================================================================
# 4. SOURCE DATA
# ============================================================================


async def list_source_data(
    limit: int = Query(50, le=100),
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.SourceDocumentsResponse:
    """GET /api/admin/source-data/list - List uploaded files"""

    query = (
        select(DBSourceDocument)
        .order_by(DBSourceDocument.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    source_documents: list[DBSourceDocument] = result.scalars().all()

    return w.SourceDocumentsResponse(
        files=[await source_document.to_bm() for source_document in source_documents]
    )
