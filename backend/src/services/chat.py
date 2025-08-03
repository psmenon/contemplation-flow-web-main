from tuneapi import tt, ta, tu

import uuid
from asyncio import sleep
from textwrap import dedent
from supabase import Client
from sqlalchemy import select, desc, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends, Query, HTTPException
from fastapi.responses import StreamingResponse


from src import wire as w, settings, db
from src.settings import get_supabase_client
from src.db import get_db_session_fa
from src.dependencies import get_current_user


# Mock data and functions for testing
async def _mock_llm_chat(
    session: AsyncSession,
    model: tt.ModelInterface,
    master_thread: tt.Thread,
    conversation: db.Conversation,
    spb_client: Client,
):
    """Mock version of _llm_chat that simulates LLM responses without actual API calls"""

    # Mock response text
    mock_response = "Thank you for your question about spiritual practice. Based on the teachings I've reviewed, I can share some insights about mindfulness and contemplation. The path of spiritual growth involves both inner reflection and outward compassion. Would you like to explore this topic further?"

    # Simulate processing time
    st_ns = tu.SimplerTimes.get_now_fp64()

    # Yield chunks to simulate streaming
    words = mock_response.split()
    for i, word in enumerate(words):
        if i == 0:
            yield ta.to_openai_chunk(tt.assistant(word))
        else:
            yield ta.to_openai_chunk(tt.assistant(" " + word))
        await sleep(0.05)

    # Create mock AI message
    ai_message = db.Message(
        conversation_id=conversation.id,
        role=db.MessageRole.ASSISTANT,
        content=mock_response,
        input_tokens=150,  # Mock values
        output_tokens=75,
        processing_time_ms=int((tu.SimplerTimes.get_now_fp64() - st_ns) * 1000),
        model_used="mock-gpt-4o",
    )
    session.add(ai_message)
    await session.commit()
    await session.refresh(ai_message)
    yield ta.to_openai_chunk(tt.assistant(f"<message_id>{ai_message.id}</message_id>"))

    # Mock citations
    mock_citations = [
        w.CitationInfo(
            name="spiritual_teachings.pdf",
            url="https://mfzbpincchxrgqwagpjw.supabase.co/storage/v1/object/sign/source-files/Sadhanas-from-Devikalottara-Jnanachara-Vichara-Patalah.pdf?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV9jMTI5OWE2YS05ZWI4LTRkMGEtOGE5My03MGRhZTk1ZGMwNmMiLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJzb3VyY2UtZmlsZXMvU2FkaGFuYXMtZnJvbS1EZXZpa2Fsb3R0YXJhLUpuYW5hY2hhcmEtVmljaGFyYS1QYXRhbGFoLnBkZiIsImlhdCI6MTc1MTk5NzkwMSwiZXhwIjoxNzgzNTMzOTAxfQ.fAJDi47vDS72U5nm3dZ8kgz93l6VYWE0WcqIUrNwQGQ",
        ),
        w.CitationInfo(
            name="meditation_guide.pdf",
            url="https://mfzbpincchxrgqwagpjw.supabase.co/storage/v1/object/sign/source-files/Sadhanas-from-Devikalottara-Jnanachara-Vichara-Patalah.pdf?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV9jMTI5OWE2YS05ZWI4LTRkMGEtOGE5My03MGRhZTk1ZGMwNmMiLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJzb3VyY2UtZmlsZXMvU2FkaGFuYXMtZnJvbS1EZXZpa2Fsb3R0YXJhLUpuYW5hY2hhcmEtVmljaGFyYS1QYXRhbGFoLnBkZiIsImlhdCI6MTc1MTk5NzkwMSwiZXhwIjoxNzgzNTMzOTAxfQ.fAJDi47vDS72U5nm3dZ8kgz93l6VYWE0WcqIUrNwQGQ",
        ),
    ]

    ai_message.citations = mock_citations
    await session.commit()
    await session.refresh(ai_message)

    yield ta.to_openai_chunk(tt.assistant(f"<citations>"))
    for c in mock_citations:
        yield ta.to_openai_chunk(tt.assistant(tu.to_json(c.model_dump(), tight=True)))
    yield ta.to_openai_chunk(tt.assistant("</citations>"))

    # Mock follow up questions
    mock_follow_up = w.FollowUpQuestions(
        questions=[
            "How can I develop a daily mindfulness practice?",
            "What are the key principles of spiritual contemplation?",
            "How do I balance inner reflection with daily responsibilities?",
        ]
    )

    ai_message.follow_up_questions = mock_follow_up
    await session.commit()
    await session.refresh(ai_message)

    yield ta.to_openai_chunk(tt.assistant("<questions>"))
    for q in mock_follow_up.questions:
        yield ta.to_openai_chunk(tt.assistant(q))
    yield ta.to_openai_chunk(tt.assistant("</questions>"))

    # Mock title generation if conversation has no title
    if not conversation.title:
        conversation.title = "[Mock] - Spiritual Practice Discussion"
        await session.commit()
        yield ta.to_openai_chunk(
            tt.assistant(f"<title>[Mock] - Spiritual Practice Discussion</title>")
        )

    # Yield closing message
    yield "[DONE]\n\n"


async def _mock_embedding_search(
    session: AsyncSession,
    model: tt.ModelInterface,
    query: str,
) -> list[tuple[str, str]]:
    """Mock version of embedding search that returns predefined chunks"""
    mock_chunks = [
        (
            "Mindfulness is the practice of being fully present and engaged with whatever we're doing at the moment — free from distraction or judgment, and aware of where we are and what we're doing.",
            "test-mindfulness_basics.pdf",
        ),
        (
            "The journey inward requires patience and compassion with oneself. True spiritual growth happens gradually through consistent practice and genuine inquiry.",
            "test-spiritual_teachings.pdf",
        ),
        (
            "In meditation, we learn to observe our thoughts without being caught by them. This creates space for wisdom and peace to emerge naturally.",
            "test-meditation_guide.pdf",
        ),
        (
            "Contemplation involves deep reflection on spiritual truths. It is not just thinking about them, but allowing them to permeate our being and transform our understanding.",
            "test-contemplation_practices.pdf",
        ),
        (
            "The interconnectedness of all beings becomes apparent when we quiet the mind and open the heart. This recognition leads to natural compassion.",
            "test-unity_teachings.pdf",
        ),
    ]
    return mock_chunks


async def create_mock_database_entries(
    session: AsyncSession,
) -> tuple[db.UserProfile, db.Conversation]:
    """Create mock database entries for testing"""

    # Create mock user
    mock_user = db.UserProfile(
        id=uuid.uuid4(),
        phone_number="+1234567890",
        phone_verified=True,
        name="Mock User",
        role=db.UserRole.USER,
        is_signed_in=True,
    )
    session.add(mock_user)
    await session.commit()
    await session.refresh(mock_user)

    # Create mock conversation
    conversation_id = str(uuid.uuid4())
    mock_conversation = db.Conversation(
        id=conversation_id, user_id=mock_user.id, title=None  # Will be generated
    )
    session.add(mock_conversation)
    await session.commit()
    await session.refresh(mock_conversation)

    # Create mock source documents
    mock_source_docs = [
        db.SourceDocument(
            id=uuid.uuid4(),
            filename="mindfulness_basics.pdf",
            file_size_bytes=1048576,
            active=True,
            status=db.DocumentStatus.COMPLETED,
        ),
        db.SourceDocument(
            id=uuid.uuid4(),
            filename="spiritual_teachings.pdf",
            file_size_bytes=2097152,
            active=True,
            status=db.DocumentStatus.COMPLETED,
        ),
        db.SourceDocument(
            id=uuid.uuid4(),
            filename="meditation_guide.pdf",
            file_size_bytes=1572864,
            active=True,
            status=db.DocumentStatus.COMPLETED,
        ),
    ]

    for doc in mock_source_docs:
        session.add(doc)
    await session.commit()

    # Create mock document chunks with dummy embeddings
    mock_embeddings = [
        [0.1] * 1536,
        [0.2] * 1536,
        [0.3] * 1536,
        [0.4] * 1536,
        [0.5] * 1536,
    ]
    mock_chunks_data = [
        ("Mindfulness is the practice of being fully present...", "Page 1"),
        ("The journey inward requires patience and compassion...", "Page 5"),
        ("In meditation, we learn to observe our thoughts...", "Page 12"),
        ("Contemplation involves deep reflection on spiritual truths...", "Page 8"),
        ("The interconnectedness of all beings becomes apparent...", "Page 15"),
    ]

    for i, (content, location) in enumerate(mock_chunks_data):
        chunk = db.DocumentChunk(
            id=uuid.uuid4(),
            source_document_id=mock_source_docs[i % len(mock_source_docs)].id,
            content=content,
            embedding=mock_embeddings[i],
            location=location,
            model_used="mock-text-embedding-3-small",
        )
        session.add(chunk)

    await session.commit()

    return mock_user, mock_conversation


async def _llm_chat(
    session: AsyncSession,
    model: tt.ModelInterface,
    master_thread: tt.Thread,
    conversation: db.Conversation,
    spb_client: Client,
):
    llm_response = ""
    usage: tt.Usage | None = None
    st_ns = tu.SimplerTimes.get_now_fp64()
    async for chunk in model.stream_chat_async(master_thread, usage=True):
        if isinstance(chunk, tt.Usage):
            usage = chunk
        else:
            # yield the chunk
            llm_response += chunk
            yield ta.to_openai_chunk(tt.assistant(chunk))

    # insert a new message into the conversation
    ai_message = db.Message(
        conversation_id=conversation.id,
        role=db.MessageRole.ASSISTANT,
        content=llm_response,
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
        processing_time_ms=int((tu.SimplerTimes.get_now_fp64() - st_ns) * 1000),
        model_used=model.model_id,
    )
    session.add(ai_message)
    await session.commit()
    await session.refresh(ai_message)
    yield ta.to_openai_chunk(tt.assistant(f"<message_id>{ai_message.id}</message_id>"))

    # ---------------------------- find the relevant documents ----------------------------
    class DocumentList(tt.BM):
        document_names: list[str] = tt.F(
            "The names of the documents that are relevant to the query"
        )

    document_search_thread = master_thread.copy()
    document_search_thread.append(
        tt.human("Give me the list of documents that are relevant to the query")
    )
    document_search_thread.schema = DocumentList
    resp_docs_list: DocumentList
    usage_docs_list: tt.Usage
    resp_docs_list, usage_docs_list = await model.chat_async(
        document_search_thread,
        usage=True,
    )
    if usage_docs_list:
        ai_message.input_tokens = usage_docs_list.input_tokens + ai_message.input_tokens
        ai_message.output_tokens = (
            usage_docs_list.output_tokens + ai_message.output_tokens
        )

    # DB query to get the documents
    query = select(db.SourceDocument).where(
        db.SourceDocument.filename.in_(resp_docs_list.document_names)
    )
    result = await session.execute(query)
    documents: list[db.SourceDocument] = result.scalars().all()

    # Generate presigned URLs for documents
    citations = []
    for d in documents:
        try:
            # Generate presigned URL valid for 1 hour
            presigned_response = spb_client.storage.from_(
                "source-files"
            ).create_signed_url(
                d.filename,
                3600,
                {"download": False},
            )  # 1 hour expiry, open in browser

            if presigned_response.get("error"):
                # Fallback to filename if URL generation fails
                url = d.filename
            else:
                url = presigned_response.get("signedURL", d.filename)

            citations.append(w.CitationInfo(name=d.filename, url=url))
        except Exception:
            # Fallback to filename if any error occurs
            citations.append(w.CitationInfo(name=d.filename, url=d.filename))

    ai_message.citations = citations
    await session.commit()
    await session.refresh(ai_message)

    yield ta.to_openai_chunk(tt.assistant(f"<citations>"))
    for c in citations:
        yield ta.to_openai_chunk(tt.assistant(tu.to_json(c.model_dump(), tight=True)))
    yield ta.to_openai_chunk(tt.assistant("</citations>"))

    # ---------------------------- create follow up questions ----------------------------
    follow_up_thread = master_thread.copy()
    follow_up_thread.append(tt.assistant(llm_response))
    follow_up_thread.append(
        tt.human(
            dedent(
                """
            ----

            You are given a conversation till now.

            Your task is to generate is to generate 3 follow up questions that you think would be a
            good idea considering this is a Spiritual AI assistant.
            """.strip()
            )
        )
    )
    follow_up_thread.schema = w.FollowUpQuestions
    follow_up_resp: w.FollowUpQuestions
    usage_follow_up: tt.Usage
    follow_up_resp, usage_follow_up = await model.chat_async(
        follow_up_thread, usage=True
    )
    if usage_follow_up:
        ai_message.input_tokens = usage_follow_up.input_tokens + ai_message.input_tokens
        ai_message.output_tokens = (
            usage_follow_up.output_tokens + ai_message.output_tokens
        )
    ai_message.follow_up_questions = follow_up_resp
    await session.commit()
    await session.refresh(ai_message)

    yield ta.to_openai_chunk(tt.assistant("<questions>"))
    for q in follow_up_resp.questions:
        yield ta.to_openai_chunk(tt.assistant(q))
    yield ta.to_openai_chunk(tt.assistant("</questions>"))

    # ---------------------------- create title for the conversation ----------------------------
    # if this is a new conversation, then we also need to assign a title to it
    print(">>>>>", conversation.title)
    if not conversation.title:

        class TitleRequest(tt.BM):
            title: str = tt.F("Title for the conversation")

        title_thread = tt.Thread(
            tt.human(
                dedent(
                    f"""
                You are given a user message and the response, give a good title with verb on the same line.
                User message: {master_thread.chats[-1].value}
                Response: {llm_response}

                It should be less than 4 words and should have an action like vibe.
                """
                )
            ),
            schema=TitleRequest,
        )
        title_resp: TitleRequest
        usage_title: tt.Usage
        title_resp, usage_title = await model.chat_async(title_thread, usage=True)
        if usage_title:
            ai_message.input_tokens = usage_title.input_tokens + ai_message.input_tokens
            ai_message.output_tokens = (
                usage_title.output_tokens + ai_message.output_tokens
            )

        # udpate the title in the DB
        tu.logger.info(f"New conversation title: {title_resp.title}")

        query = select(db.Conversation).where(db.Conversation.id == conversation.id)
        result = await session.execute(query)
        conversation: db.Conversation | None = result.scalar_one_or_none()
        if conversation:
            conversation.title = title_resp.title
            await session.commit()
            await session.refresh(conversation)

        tu.logger.info(f"title: {conversation.title}")
        yield ta.to_openai_chunk(tt.assistant(f"<title>{title_resp.title}</title>"))

    # yield the closing message
    yield "[DONE]\n\n"


async def _embedding_search(
    session: AsyncSession,
    model: tt.ModelInterface,
    query: str,
) -> list[tuple[str, str]]:
    """
    Search the embedding database for the most relevant chunks
    """
    embedding_response = await model.embedding_async(
        query, model="text-embedding-3-small"
    )
    embedding = embedding_response.embedding[0]

    # search the database
    query = (
        select(db.DocumentChunk.content, db.SourceDocument.filename)
        .join(db.SourceDocument)
        .where(db.SourceDocument.active == True)
        .order_by(db.DocumentChunk.embedding.max_inner_product(embedding))
        .limit(10)
    )
    result = await session.execute(query)
    chunks: list[tuple[str, str]] = result.all()
    return chunks


# Chat endpoint
async def chat_completions(
    conversation_id: str,
    request: w.ChatCompletionRequest,
    user: db.UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_client),
):
    """POST /api/chat/completions - OpenAI compatible streaming chat endpoint."""
    # get the conversation
    query = select(db.Conversation).where(
        db.Conversation.id == conversation_id,
        db.Conversation.user_id == user.id,
    )
    result = await session.execute(query)
    conversation: db.Conversation | None = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # create thread
    master_thread = tt.Thread(
        tt.system(f"The current time is {tu.SimplerTimes.get_now_human()}"),
        id=conversation_id,
    )

    # Get all the messages in the conversation in ascending order
    query = (
        select(db.Message)
        .where(db.Message.conversation_id == conversation_id)
        .order_by(db.Message.created_at)
    )
    result = await session.execute(query)
    conversation_messages: list[db.Message] = result.scalars().all()
    for m in conversation_messages:
        master_thread.append(tt.Message(m.content, m.role.value))

    # Insert a new message into the conversation
    user_message = db.Message(
        conversation_id=conversation_id,
        role=db.MessageRole.USER,
        content=request.message,
    )
    session.add(user_message)
    await session.commit()

    # Choose between mock and real implementations
    if request.mock:
        # Use mock functions
        model = None  # Not needed for mock
        chunks = await _mock_embedding_search(session, model, request.message)

        chunk_text = (
            "Here's all the chunks from the database that are relevant to the query:\n"
        )
        for c_content, c_fname in chunks:
            chunk_text += f"<filename> {c_fname} </filename>\n"
            chunk_text += f"<content> {c_content} </content>\n"
            chunk_text += f"--------------------------------\n"

        # update the master thread with the request message and the chunks
        master_thread.append(tt.human("Find similar chunks from the database"))
        master_thread.append(tt.assistant(chunk_text))
        master_thread.append(
            tt.human(
                dedent(
                    f"""
                You are given a conversation till now and some relevant chunks from the database.
                Your task is to generate a response to the user's message considering the chunks if required.
                You will respond in a first person narrative conversational way as if you have understood the idea
                and are now sharing your thoughts. You will never bring up chunks to the user.

                Question:
                {request.message}
                """.strip()
                )
            ),
        )

        # chat with the mock model
        resp = _mock_llm_chat(
            session=session,
            model=model,
            master_thread=master_thread,
            conversation=conversation,
            spb_client=spb_client,
        )
    else:
        # Use real implementations
        # create the model interface
        model = settings.get_llm("gpt-4o")

        # get the relevant chunks
        chunks = await _embedding_search(session, model, request.message)
        chunk_text = (
            "Here's all the chunks from the database that are relevant to the query:\n"
        )
        for c_content, c_fname in chunks:
            chunk_text += f"<filename> {c_fname} </filename>\n"
            chunk_text += f"<content> {c_content} </content>\n"
            chunk_text += f"--------------------------------\n"

        # update the master thread with the request message and the chunks
        master_thread.append(tt.human("Find similar chunks from the database"))
        master_thread.append(tt.assistant(chunk_text))
        master_thread.append(
            tt.human(
                dedent(
                    f"""
                You are given a conversation till now and some relevant chunks from the database.
                Your task is to generate a response to the user's message considering the chunks if required.

                Question:
                {request.message}

                """.strip()
                )
            )
        )

        # chat with the model
        resp = _llm_chat(
            session=session,
            model=model,
            master_thread=master_thread,
            conversation=conversation,
            spb_client=spb_client,
        )

    if request.stream:
        return StreamingResponse(
            resp,
            media_type="text/event-stream",
        )
    else:
        q_ongoing = False
        questions = []
        output = ""
        message_id = ""
        citations = []
        c_ongoing = False
        title = None
        async for chunk in resp:
            if type(chunk) == str and not chunk.startswith("["):
                chunk = tu.from_json(chunk[5:].strip())
                content = chunk["choices"][0]["delta"]["content"].strip()
                if q_ongoing:
                    if content.startswith("</questions>"):
                        q_ongoing = False
                    else:
                        questions.append(content)
                elif content.startswith("<questions>"):
                    q_ongoing = True
                elif content.startswith("<message_id>"):
                    message_id = content[12:-13]
                elif content.startswith("<title>"):
                    title = content[8:-9]
                elif content.startswith("<citations>"):
                    c_ongoing = True
                elif content.startswith("</citations>"):
                    c_ongoing = False
                elif c_ongoing:
                    citations.append(tu.from_json(content))
                else:
                    output += " " + content
        return w.ChatCompletionResponse(
            message_id=message_id,
            message=output,
            questions=questions,
            citations=citations,
            title=title,
        )


# Conversation Management
async def create_conversation(
    request: w.CreateConversationRequest,
    session: AsyncSession = Depends(get_db_session_fa),
    user: db.UserProfile = Depends(get_current_user),
) -> w.Conversation:
    """POST /api/conversations - Create a new conversation"""
    conversation_id = str(uuid.uuid4())
    new_conversation = db.Conversation(id=conversation_id, user_id=user.id)
    session.add(new_conversation)
    for m in request.messages:
        new_message = db.Message(
            conversation_id=new_conversation.id,
            role=db.MessageRole.USER,
            content=m.content,
        )
        session.add(new_message)
    await session.commit()
    await session.refresh(new_conversation)

    return await new_conversation.to_bm()


async def get_conversations(
    limit: int = Query(10, le=50),
    offset: int = Query(0),
    session: AsyncSession = Depends(get_db_session_fa),
    user: db.UserProfile = Depends(get_current_user),
) -> w.ConversationsListResponse:
    """GET /api/conversations - List user's conversations"""
    query = (
        select(db.Conversation)
        .where(db.Conversation.user_id == user.id)
        .where(db.Conversation.deleted_at == None)  # noqa: E711
        .order_by(desc(db.Conversation.updated_at))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    conversations: list[db.Conversation] = result.scalars().all()
    return w.ConversationsListResponse(
        conversations=[await c.to_bm() for c in conversations]
    )


async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_db_session_fa),
    user: db.UserProfile = Depends(get_current_user),
    spb_client: Client = Depends(get_supabase_client),
) -> w.ConversationDetailResponse:
    """GET /api/conversations/{id} - Get conversation with messages and content"""
    query = (
        select(db.Conversation)
        .where(
            db.Conversation.id == conversation_id,
            db.Conversation.user_id == user.id,
            db.Conversation.deleted_at == None,  # noqa: E711
        )
        .options(selectinload(db.Conversation.messages))  # eager load messages
    )
    result = await session.execute(query)
    conversation: db.Conversation | None = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # get the content generations
    query = select(db.ContentGeneration).where(
        db.ContentGeneration.conversation_id == conversation_id
    )
    result = await session.execute(query)
    content_generations: list[db.ContentGeneration] = result.scalars().all()

    # load presigned urls for the content generations
    content_generations_with_urls = []
    for cg in content_generations:
        content_item = await cg.to_bm()
        if cg.content_path:
            try:
                # Generate presigned URL for download (expires in 1 hour)
                presigned_response = spb_client.storage.from_(
                    "generations"
                ).create_signed_url(
                    cg.content_path, 3600  # 1 hour expiry
                )

                if presigned_response.get("error"):
                    content_item.content_url = (
                        None  # Set to None if URL generation fails
                    )
                else:
                    content_item.content_url = presigned_response.get("signedURL")
            except Exception:
                content_item.content_url = None  # Set to None if any error occurs
        else:
            content_item.content_url = None  # No content path available

        content_generations_with_urls.append(content_item)

    return w.ConversationDetailResponse(
        conversation=await conversation.to_bm(),
        messages=[
            await m.to_bm()
            for m in sorted(conversation.messages, key=lambda x: x.created_at)
        ],
        content_generations=content_generations_with_urls,
    )


async def update_conversation_title(
    conversation_id: str,
    request: w.UpdateConversationTitleRequest,
    session: AsyncSession = Depends(get_db_session_fa),
    user: db.UserProfile = Depends(get_current_user),
) -> w.Conversation:
    """PUT /api/conversations/{id}/title - Update conversation title"""
    query = select(db.Conversation).where(
        db.Conversation.id == conversation_id,
        db.Conversation.user_id == user.id,
    )
    result = await session.execute(query)
    conversation: db.Conversation | None = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.title = request.title
    await session.commit()
    await session.refresh(conversation)
    return await conversation.to_bm()


async def delete_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_db_session_fa),
    user: db.UserProfile = Depends(get_current_user),
) -> w.SuccessResponse:
    """DELETE /api/conversations/{id} - Delete conversation and all content"""
    query = select(db.Conversation).where(
        db.Conversation.id == conversation_id,
        db.Conversation.user_id == user.id,
    )
    result = await session.execute(query)
    conversation: db.Conversation | None = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.deleted_at = tu.SimplerTimes.get_now_datetime()

    await session.commit()
    return w.SuccessResponse(success=True, message="Conversation deleted", data={})


async def submit_conversation_feedback(
    conversation_id: str,
    request: w.MessageFeedbackRequest,
    session: AsyncSession = Depends(get_db_session_fa),
    user: db.UserProfile = Depends(get_current_user),
) -> w.SuccessResponse:
    """POST /api/conversations/{id}/feedback - Submit message feedback"""
    feedback_type = db.FeedbackType(request.type)
    if feedback_type not in [db.FeedbackType.POSITIVE, db.FeedbackType.NEGATIVE]:
        raise HTTPException(
            status_code=400,
            detail="Invalid feedback type, must be positive or negative. Got: "
            + request.type,
        )

    # Verify user owns the conversation
    query_conv = select(db.Conversation).where(
        db.Conversation.id == conversation_id,
        db.Conversation.user_id == user.id,
    )
    result_conv = await session.execute(query_conv)
    conversation: db.Conversation | None = result_conv.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    query = select(db.Message).where(
        db.Message.id == request.message_id,
        db.Message.conversation_id == conversation_id,
    )
    result = await session.execute(query)
    message: db.Message | None = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.feedback_given_at = tu.SimplerTimes.get_now_datetime()
    message.feedback_type = db.FeedbackType(request.type)
    if request.comment:
        message.feedback_comment = request.comment
    await session.commit()
    return w.SuccessResponse(success=True, message="Feedback submitted")
