from typing import AsyncGenerator, Annotated, ClassVar, Any
from tuneapi import tu, tt

import datetime
from uuid import uuid4
from fastapi import Request
from ssl import create_default_context
import enum

from sqlalchemy import (
    UUID as SQLAlchemyUUID,
    DateTime,
    Dialect,
    func,
    Index,
    FetchedValue,
    NullPool,
    exc,
    String,
    create_engine,
    Engine,
    ForeignKey,
    BigInteger,
    Boolean,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    INET,
    ENUM as pg_enum,
)
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncAttrs,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)

from sqlalchemy.orm import (
    sessionmaker,
    DeclarativeBase,
    Mapped,
    mapped_column,
    Session,
    relationship,
)
from sqlalchemy.types import TypeDecorator
from sqlalchemy import MetaData

from src.settings import settings
from src import wire


# column declarations

default_timestamp = Annotated[
    datetime.datetime,
    mapped_column(
        DateTime(timezone=True),
        default=func.timezone("UTC", func.statement_timestamp()),
    ),
]

updated_timestamp = Annotated[
    datetime.datetime,
    mapped_column(
        DateTime(timezone=True),
        default=func.timezone("UTC", func.statement_timestamp()),
        onupdate=func.timezone("UTC", func.statement_timestamp()),
        server_onupdate=FetchedValue(),
    ),
]

pkey_uuid = Annotated[
    SQLAlchemyUUID,
    mapped_column(SQLAlchemyUUID(), primary_key=True, default=uuid4),
]

fkey_uuid = Annotated[
    SQLAlchemyUUID,
    mapped_column(SQLAlchemyUUID()),
]

uuid_key = Annotated[
    SQLAlchemyUUID,
    mapped_column(SQLAlchemyUUID()),
]


# Define the Base class
meta = MetaData()


class Base(AsyncAttrs, DeclarativeBase):
    metadata: ClassVar = meta
    type_annotation_map: ClassVar = {dict[str, Any]: JSONB}


# Define helpers for columns
class PydanticList(TypeDecorator[list[tt.BM]]):
    """
    Enables JSON storage of list of Pydantic models.

    Use like this:

    ... my_field: Mapped[list[MyPydanticModel] | None] = mapped_column(
            PydanticList(MyPydanticModel),
            nullable=True,
            default=None,
        )
    """

    impl = JSONB
    cache_ok = True

    def __init__(self, model_class: type[tt.BM], **kwargs):
        super().__init__(**kwargs)
        self.model_class = model_class

    def process_bind_param(
        self, value: list[tt.BM] | None, dialect: Dialect
    ) -> list[dict[str, Any]]:
        if value is None:
            return None
        return [item.model_dump() for item in value]

    def process_result_value(
        self, value: list[dict[str, Any]] | None, dialect: Dialect
    ) -> list[tt.BM]:
        if value is None:
            return None
        return [self.model_class.model_validate(item) for item in value]


class PydanticModel(TypeDecorator[tt.BM]):
    """
    Enables JSON storage of a single Pydantic model.

    Use like this:

    ... my_field: Mapped[MyPydanticModel | None] = mapped_column(
            PydanticModel(MyPydanticModel),
            nullable=True,
            default=None,
        )
    """

    impl = JSONB
    cache_ok = True

    def __init__(self, model_class: type[tt.BM], **kwargs):
        super().__init__(**kwargs)
        self.model_class = model_class

    def process_bind_param(
        self,
        value: tt.BM | None,
        *a,
        **k,
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        return value.model_dump()

    def process_result_value(
        self,
        value: dict[str, Any] | None,
        *a,
        **k,
    ) -> tt.BM | None:
        if value is None:
            return None
        return self.model_class.model_validate(value)


def connect_to_postgres(sync: bool = False) -> AsyncEngine | Engine:
    ssl_context = create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = settings.prod  # Set to True in production
    if sync:
        return create_engine(
            str(settings.db_url),
            echo=settings.echo_db,
            echo_pool=True,
            pool_pre_ping=True,
            pool_recycle=3600,  # Recycle connections every hour
            connect_args={"ssl": ssl_context},
        )
    return create_async_engine(
        str(settings.db_url),
        echo=settings.echo_db,
        echo_pool=True,
        pool_pre_ping=True,
        pool_recycle=3600,  # Recycle connections every hour
        connect_args={"ssl": ssl_context},
    )


def get_db_session(
    sync: bool = False,
) -> AsyncSession | Session:
    db_engine = connect_to_postgres(sync=sync)
    if sync:
        factory = sessionmaker(db_engine, expire_on_commit=False)
    else:
        factory = async_sessionmaker(db_engine, expire_on_commit=False)
    return factory()


async def get_db_session_fa(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session: AsyncSession = request.app.state.db_session_factory()

    try:
        yield session
    except Exception as e:
        tu.logger.error(f"Error in db session: {e}")
        await session.rollback()
        raise  # Re-raise the exception so FastAPI can handle it properly
    else:
        try:
            await session.commit()
        except exc.SQLAlchemyError as e:
            tu.logger.error(f"Error in db session: {e}")
            await session.rollback()
            raise  # Re-raise the exception so FastAPI can handle it properly
        finally:
            await session.close()
    finally:
        await session.close()


# ============================================================================
# 1. USER MANAGEMENT TABLES
# ============================================================================


# Enum definitions for database constraints
class UserRole(enum.Enum):
    USER = "user"
    ADMIN = "admin"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[pkey_uuid] = mapped_column(primary_key=True)
    created_at: Mapped[default_timestamp]
    updated_at: Mapped[updated_timestamp]
    last_active_at: Mapped[default_timestamp]
    phone_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, name="user_role_enum", create_type=True),
        default=UserRole.USER,
        nullable=False,
    )
    is_signed_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    content_generations: Mapped[list["ContentGeneration"]] = relationship(
        "ContentGeneration", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = ()

    async def to_bm(self) -> wire.User:
        return wire.User(
            id=str(self.id),
            phone_number=self.phone_number,
            phone_verified=self.phone_verified,
            name=self.name,
            role=self.role.value,
            last_active=self.last_active_at,
            created_at=self.created_at,
        )


class OTPSessionType(enum.Enum):
    REGISTER = "register"
    LOGIN = "login"
    VERIFICATION = "verification"


class OTPStatus(enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    FAILED = "failed"


class OTPSession(Base):
    __tablename__ = "otp_sessions"

    id: Mapped[pkey_uuid]
    phone_number: Mapped[str] = mapped_column(String, nullable=False)
    otpless_request_id: Mapped[str] = mapped_column(String, nullable=False)
    session_type: Mapped[OTPSessionType] = mapped_column(
        pg_enum(OTPSessionType, name="otp_session_type_enum", create_type=True),
        nullable=False,
    )
    status: Mapped[OTPStatus] = mapped_column(
        pg_enum(OTPStatus, name="otp_status_enum", create_type=True),
        default=OTPStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[default_timestamp]
    verified_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = ()


# ============================================================================
# 2. CHAT & CONVERSATIONS TABLES
# ============================================================================


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[pkey_uuid]
    created_at: Mapped[default_timestamp]
    updated_at: Mapped[updated_timestamp]
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    user_id: Mapped[fkey_uuid] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE")
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    user: Mapped["UserProfile"] = relationship(
        "UserProfile", back_populates="conversations"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    content_generations: Mapped[list["ContentGeneration"]] = relationship(
        "ContentGeneration", back_populates="conversation"
    )

    __table_args__ = ()

    async def to_bm(self) -> wire.Conversation:
        return wire.Conversation(
            id=str(self.id),
            user_id=str(self.user_id),
            title=self.title,
            created_at=self.created_at,
        )


class MessageRole(enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class FeedbackType(enum.Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[pkey_uuid]
    created_at: Mapped[default_timestamp]
    conversation_id: Mapped[fkey_uuid] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[MessageRole] = mapped_column(
        pg_enum(MessageRole, name="message_role_enum", create_type=True),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[wire.CitationInfo] | None] = mapped_column(
        PydanticList(wire.CitationInfo), default=list
    )
    follow_up_questions: Mapped[wire.FollowUpQuestions | None] = mapped_column(
        PydanticModel(wire.FollowUpQuestions), default=None
    )
    feedback_type: Mapped[FeedbackType] = mapped_column(
        pg_enum(FeedbackType, name="feedback_type_enum", create_type=True),
        nullable=True,
    )
    feedback_given_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    feedback_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Store metadata for the calculating LLM pricing
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )
    content_generations: Mapped[list["ContentGeneration"]] = relationship(
        "ContentGeneration", back_populates="message"
    )

    __table_args__ = ()

    async def to_bm(self) -> wire.Message:
        return wire.Message(
            id=str(self.id),
            role=self.role.value,
            created_at=self.created_at,
            content=self.content,
            citations=self.citations,
            follow_up_questions=self.follow_up_questions,
        )


# ============================================================================
# 3. DOCUMENT MANAGEMENT TABLES
# ============================================================================


class DocumentStatus(enum.Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[pkey_uuid]
    created_at: Mapped[default_timestamp]
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        pg_enum(DocumentStatus, name="document_status_enum", create_type=True),
        default=DocumentStatus.PROCESSING,
    )

    # Relationships
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="source_document", cascade="all, delete-orphan"
    )

    __table_args__ = ()

    async def to_bm(self) -> wire.SourceDocument:
        return wire.SourceDocument(
            id=str(self.id),
            filename=self.filename,
            file_size_bytes=self.file_size_bytes,
            active=self.active,
            status=self.status.value,
            created_at=self.created_at,
        )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[pkey_uuid]
    created_at: Mapped[default_timestamp]
    updated_at: Mapped[updated_timestamp]
    source_document_id: Mapped[fkey_uuid] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(1536), nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships
    source_document: Mapped["SourceDocument"] = relationship(
        "SourceDocument", back_populates="chunks"
    )

    __table_args__ = ()


# ============================================================================
# 4. CONTENT GENERATION TABLES
# ============================================================================


class ContentType(enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class ContentGeneration(Base):
    __tablename__ = "content_generations"

    id: Mapped[pkey_uuid]
    created_at: Mapped[default_timestamp]
    user_id: Mapped[fkey_uuid] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[fkey_uuid] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=False
    )
    message_id: Mapped[fkey_uuid] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=False
    )
    content_type: Mapped[ContentType] = mapped_column(
        pg_enum(ContentType, name="content_type_enum", create_type=True),
        nullable=False,
    )
    # supabase path
    content_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # Contemplation card text and theme
    cc_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cc_theme: Mapped[str | None] = mapped_column(String, nullable=True)

    # The following are the
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    voice_id: Mapped[str | None] = mapped_column(String, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["UserProfile"] = relationship(
        "UserProfile", back_populates="content_generations"
    )
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="content_generations"
    )
    message: Mapped["Message"] = relationship(
        "Message", back_populates="content_generations"
    )

    __table_args__ = ()

    async def to_bm(self) -> wire.ContentGeneration:
        return wire.ContentGeneration(
            id=str(self.id),
            status="complete" if self.content_path else "processing",
            conversation_id=str(self.conversation_id),
            message_id=str(self.message_id),
            content_type=self.content_type.value,
            content_url=self.content_path,
            created_at=self.created_at,
            transcript=self.transcript,
        )


# ============================================================================
# 5. INDEXES
# ============================================================================

# Create indexes for performance
Index("idx_source_documents_active", SourceDocument.active, SourceDocument.status)
Index("idx_otp_sessions_phone_expires", OTPSession.phone_number, OTPSession.expires_at)
Index("idx_user_profiles_phone", UserProfile.phone_number)
Index(
    "idx_content_generations_user_created",
    ContentGeneration.user_id,
    ContentGeneration.created_at,
)
Index("idx_content_generations_type", ContentGeneration.content_type)
