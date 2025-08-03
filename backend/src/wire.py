# Authentication Interfaces

import datetime
from tuneapi import tt


# User Management Interfaces
class User(tt.BM):
    id: str = tt.F("Unique user identifier")
    phone_number: str = tt.F("User's phone number")
    phone_verified: bool = tt.F("Whether user's phone number is verified")
    name: str | None = tt.F("User's display name")
    role: str = tt.F("User role: user or admin")
    created_at: datetime.datetime = tt.F("ISO timestamp of account creation")
    last_active: datetime.datetime = tt.F("ISO timestamp of last active")


class NewUserRequest(tt.BM):
    phone_number: str = tt.F("Phone number in international format")
    name: str = tt.F("User's display name")


class LoginRequest(tt.BM):
    phone_number: str = tt.F("Phone number in international format")
    otp: str | None = tt.F("OTP code for verification, required on second call", None)


class AuthResponse(tt.BM):
    access_token: str = tt.F("JWT access token")
    refresh_token: str = tt.F("JWT refresh token for session renewal")
    user: User | None = tt.F("User profile information")


class RefreshTokenRequest(tt.BM):
    refresh_token: str = tt.F("Refresh token to generate new access token")


# Content Generation Interfaces


class ContentGenerationRequest(tt.BM):
    conversation_id: str = tt.F("ID of conversation context for content")
    message_id: str = tt.F("ID of message that triggered generation")
    mode: str = tt.F("Generation mode: audio, video, image")


class ContentGenerationResponse(tt.BM):
    id: str = tt.F("Unique identifier for generated content")


class ContentGeneration(tt.BM):
    id: str = tt.F("Unique content identifier")
    status: str = tt.F("Processing status: processing, complete, failed")
    conversation_id: str = tt.F("ID of conversation context")
    message_id: str = tt.F("ID of message that triggered generation")
    content_type: str = tt.F("Content type: audio, video, image")
    content_url: str | None = tt.F("Presigned URL for generated content", None)
    created_at: datetime.datetime = tt.F("ISO timestamp of creation")
    transcript: str | None = tt.F("Full meditation script text")


class ContentGenerationListResponse(tt.BM):
    ids: list[str] = tt.F("List of user's content IDs")


# Speech Processing Interfaces


class TranscriptionResponse(tt.BM):
    text: str = tt.F("Transcribed text from audio input")


class TTSRequest(tt.BM):
    text: str = tt.F("Text to convert to speech")


# Chat & Conversation Interfaces
class CitationInfo(tt.BM):
    name: str = tt.F("Name of the cited document")
    url: str = tt.F("URL to view the cited document")


class FollowUpQuestions(tt.BM):
    questions: list[str] = tt.F("Follow up questions")


class Message(tt.BM):
    id: str = tt.F("Unique message identifier")
    role: str = tt.F("Message role: user, assistant")
    created_at: datetime.datetime = tt.F("ISO timestamp of message creation")
    content: str = tt.F("Message content text")
    citations: list[CitationInfo] | None = tt.F(
        "List of citations for this message", None
    )
    follow_up_questions: FollowUpQuestions | None = tt.F("Follow up questions", None)


class CreateConversationRequest(tt.BM):
    messages: list[Message] | None = tt.F("Messages to start the conversation", None)


class ChatCompletionRequest(tt.BM):
    message: str = tt.F("Message to send to the model")
    stream: bool = tt.F("Whether to stream the response")
    mock: bool = tt.F("Whether to use a mock response", False)


class ChatCompletionResponse(tt.BM):
    message: str = tt.F("Message to send to the model")
    message_id: str = tt.F("ID of the message that was sent")
    questions: list[str] | None = tt.F("Follow up questions")
    citations: list[CitationInfo] | None = tt.F("List of citations for this message")
    title: str | None = tt.F("Auto-generated or custom conversation title", None)


class Conversation(tt.BM):
    id: str = tt.F("Unique conversation identifier")
    user_id: str = tt.F("ID of the user who owns this conversation")
    title: str | None = tt.F("Auto-generated or custom conversation title")
    created_at: datetime.datetime = tt.F("ISO timestamp of conversation creation")


class ConversationsListResponse(tt.BM):
    conversations: list[Conversation] = tt.F("List of user conversations")


class ConversationDetailResponse(tt.BM):
    conversation: Conversation = tt.F("Conversation metadata")
    messages: list[Message] = tt.F("All messages in the conversation")
    content_generations: list[ContentGeneration] | None = tt.F(
        "Content generations for this conversation", None
    )


class UpdateConversationTitleRequest(tt.BM):
    title: str = tt.F("New title for the conversation")


class MessageFeedbackRequest(tt.BM):
    message_id: str = tt.F("ID of the message to provide feedback for")
    type: str = tt.F("Feedback type: positive, negative")
    comment: str | None = tt.F("Optional feedback comment")


# Admin Interfaces


class UserWithUsage(User):
    usage_stats: dict = tt.F("Usage statistics")


class ListUsersResponse(tt.BM):
    users: list[UserWithUsage] = tt.F("List of all users")


class SourceDocument(tt.BM):
    id: str = tt.F("Unique document identifier")
    filename: str = tt.F("Original filename")
    file_size_bytes: int = tt.F("File size in bytes")
    active: bool = tt.F("Whether document is active for RAG")
    status: str = tt.F("Processing status: processing, completed, failed")
    created_at: datetime.datetime = tt.F("Upload timestamp")


class SourceDocumentsResponse(tt.BM):
    files: list[SourceDocument] = tt.F("List of uploaded documents")


class UserFeedback(tt.BM):
    user_id: str = tt.F("ID of user who gave feedback")
    message_id: str = tt.F("ID of message being rated")
    type: str = tt.F("Feedback type: positive, negative")
    comment: str | None = tt.F("Feedback comment")
    created_at: datetime.datetime = tt.F("Feedback timestamp")


class AdminFeedbackResponse(tt.BM):
    feedback: list[UserFeedback] = tt.F("List of user feedback")


# API Response Wrappers


class SuccessResponse(tt.BM):
    success: bool = tt.F("Whether the operation succeeded", True)
    message: str | None = tt.F("Optional success message")
    data: dict | None = tt.F("Response data", None)


class _ErrorResponse(tt.BM):
    success: bool = tt.F("Whether the operation succeeded", False)
    code: str = tt.F("Error code identifier")
    message: str = tt.F("Human readable error message")
    details: dict | None = tt.F("Additional error details")


def Error(code: str, message: str, details: dict | None = None) -> _ErrorResponse:
    return _ErrorResponse(code=code, message=message, details=details)
