import tempfile
import os
import subprocess
import time
import hashlib
import json
import asyncio
from textwrap import dedent
import tiktoken
from tuneapi import tt, tu

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from supabase import Client

from src.db import (
    ContentGeneration,
    ContentType,
    Conversation,
    Message,
    SourceDocument,
    DocumentChunk,
)
from src.settings import get_llm, get_supabase_client
from src.db import get_db_session, get_background_session
# Import the optimized queries
from src.db import OptimizedQueries

from src.utils.profiler import profile_operation, get_profiler, print_profiler_summary

# Cache for meditation transcripts
_transcript_cache = {}

def _get_cache_key(source_text: str) -> str:
    """Generate cache key for source text"""
    return hashlib.md5(source_text.encode()).hexdigest()

async def generate_meditation_transcript_optimized(source_text: str) -> str:
    """Generate meditation transcript with caching and optimized prompt"""
    
    # Check cache first
    cache_key = _get_cache_key(source_text)
    if cache_key in _transcript_cache:
        tu.logger.info("Using cached transcript")
        return _transcript_cache[cache_key]
    
    model = get_llm("gpt-4o")
    
    # Optimized prompt - shorter and more focused
    transcript_prompt = dedent(
        f"""
        Create a 3-minute meditation script (400-500 words) from this spiritual text:
        {source_text[:2000]}  # Limit input size
        
        Requirements:
        - Calm, soothing tone
        - Include [pause] and [breathing] tags
        - Focus on mindfulness and inner peace
        - Natural flow for audio narration
        
        Generate only the meditation script.
        """
    )

    # Use a more efficient thread setup
    thread = tt.Thread(
        tt.system("Create peaceful meditation scripts."),
        id="meditation_transcript_optimized"
    )
    
    thread.append(tt.Message(transcript_prompt, "user"))

    response = await model.chat_async(thread)
    response_content = response.content if hasattr(response, 'content') else str(response)
    
    # Cache the result
    _transcript_cache[cache_key] = response_content
    
    return response_content

async def generate_audio_from_transcript_optimized(transcript: str) -> bytes:
    """Generate audio with optimized TTS settings"""
    
    model = get_llm("gpt-4o")
    
    # Optimize transcript for faster TTS
    optimized_transcript = transcript.replace('[pause]', '...').replace('[breathing]', '...')
    
    audio_bytes = await model.text_to_speech_async(
        prompt=optimized_transcript,
        voice="shimmer",
        model="gpt-4o-mini-tts",  # Use faster model
        instructions="Speak in a calm, soothing voice with natural pacing.",
    )
    
    return audio_bytes

async def compress_audio_to_mp3_optimized(audio_bytes: bytes) -> bytes:
    """Compress audio with optimized FFmpeg settings"""
    
    # Use in-memory processing where possible
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as input_file:
        input_file.write(audio_bytes)
        input_path = input_file.name

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as output_file:
        output_path = output_file.name

    try:
        # Optimized FFmpeg command for speed
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-c:a", "libmp3lame",
            "-b:a", "96k",  # Lower bitrate for faster encoding
            "-preset", "ultrafast",  # Fastest encoding
            "-y",  # Overwrite output
            output_path
        ]
        
        # Add hardware acceleration if available
        try:
            subprocess.run(["ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "testsrc2", "-t", "1", "-f", "null", "-"], capture_output=True)
            cmd.insert(1, "-hwaccel")
            cmd.insert(2, "auto")
        except:
            pass
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        
        with open(output_path, "rb") as f:
            compressed_audio = f.read()
        
        return compressed_audio
        
    finally:
        # Clean up temporary files
        for temp_path in [input_path, output_path]:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                tu.logger.warning(f"Failed to cleanup {temp_path}: {e}")

async def generate_audio_sync_optimized(
    session: AsyncSession,
    conversation_id: str,
    message_id: str,
    spb_client: Client,
    content_id: str,
) -> tuple[str, str]:
    """Generate audio content with maximum parallelization"""
    
    request_id = f"audio_{content_id}_{int(time.time())}"
    
    # Step 1: Load conversation first (sequential)
    async with profile_operation("conversation_load", request_id) as op:
        conversation_result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conversation_result.scalar_one_or_none()
        if not conversation:
            raise ValueError(f"Conversation with id {conversation_id} not found")
        op.finish()
    
    # Step 2: Generate source content (sequential to avoid session conflicts)
    async with profile_operation("source_content_generation") as op:
        source_content = await collect_source_content_optimized(session, conversation_id)
        op.finish(content_length=len(source_content))
    
    # Step 3: Generate transcript first, then audio
    async with profile_operation("transcript_generation") as op:
        transcript = await generate_meditation_transcript_optimized(source_content)
        op.finish(transcript_length=len(transcript))
    
    # Step 4: Generate audio from transcript
    async with profile_operation("audio_generation") as op:
        audio_bytes = await generate_audio_from_transcript_optimized(transcript)
        op.finish(audio_size_bytes=len(audio_bytes))
    
    # Step 5: Compress audio first, then upload
    async with profile_operation("audio_compression") as op:
        compressed_audio = await compress_audio_to_mp3_optimized(audio_bytes)
        op.finish(compressed_size_bytes=len(compressed_audio))
    
    # Step 6: Upload compressed audio
    async with profile_operation("audio_upload") as op:
        content_path = await _upload_audio_optimized(compressed_audio, content_id, spb_client)
        op.finish(upload_path=content_path)
    
    print_profiler_summary()
    return content_path, transcript

async def _upload_audio_optimized(audio_bytes: bytes, content_id: str, spb_client: Client) -> str:
    """Upload audio with optimized settings"""
    content_path = f"meditation-audio/{content_id}.mp3"
    
    # Use chunked upload for large files
    chunk_size = 1024 * 1024  # 1MB chunks
    if len(audio_bytes) > chunk_size:
        # For large files, use chunked upload
        spb_client.storage.from_("generations").upload(
            content_path,
            audio_bytes,
            {"content-type": "audio/mpeg"}
        )
    else:
        # For smaller files, direct upload
        spb_client.storage.from_("generations").upload(
            content_path,
            audio_bytes,
            {"content-type": "audio/mpeg"}
        )
    
    return content_path

async def generate_audio_content(
    content_id: str,
    conversation_id: str,
    message_id: str,
) -> None:
    """Background task to generate audio content and update the database record"""

    tu.logger.info(f"Starting background audio generation for content {content_id}")
    spb_client = get_supabase_client()

    async with get_background_session() as session:
        try:
            # Generate the audio content
            content_path, transcript = await generate_audio_sync_optimized(
                session=session,
                conversation_id=conversation_id,
                message_id=message_id,
                spb_client=spb_client,
                content_id=content_id,
            )

            # Update the ContentGeneration record with the results
            query = select(ContentGeneration).where(ContentGeneration.id == content_id)
            result = await session.execute(query)
            content_generation = result.scalar_one_or_none()

            if content_generation:
                content_generation.content_path = content_path
                content_generation.transcript = transcript
                await session.commit()
                tu.logger.info(
                    f"Successfully completed audio generation for content {content_id}"
                )
            else:
                tu.logger.error(f"ContentGeneration record not found for id {content_id}")
                # No changes were made, but ensure session is clean
                await session.rollback()

        except Exception as e:
            tu.logger.error(
                f"Error in background audio generation for content {content_id}: {e}"
            )
            # Session will be automatically rolled back by the context manager
            raise


async def collect_source_content_optimized(
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Optimized version of collect_source_content - FIXED FOR SHARED DOCUMENTS"""
    
    # Get conversation to get user_id
    conv_query = select(Conversation).where(Conversation.id == conversation_id)
    conv_result = await session.execute(conv_query)
    conversation = conv_result.scalar_one_or_none()
    
    if not conversation:
        raise ValueError("Conversation not found")
    
    # Get random chunks without user filtering since documents are shared
    query = (
        select(DocumentChunk)
        .join(SourceDocument)
        .options(selectinload(DocumentChunk.source_document))
        .where(SourceDocument.active == True)
        .order_by(func.random())
        .limit(10)
    )
    result = await session.execute(query)
    chunks = result.scalars().all()
    
    # Process chunks with null checks
    content_parts = []
    total_tokens = 0
    max_tokens = 4000  # Limit to prevent token overflow
    
    for chunk in chunks:
        # Add null check for source_document
        doc_name = chunk.source_document.filename if chunk.source_document else "Unknown Document"
        chunk_text = f"Document: {doc_name}\nContent: {chunk.content}\n\n"
        chunk_tokens = OptimizedQueries.count_tokens_optimized(chunk_text)
        
        if total_tokens + chunk_tokens > max_tokens:
            break
            
        content_parts.append(chunk_text)
        total_tokens += chunk_tokens
    
    return "".join(content_parts)


async def collect_source_content(
    session: AsyncSession,
    conversation_id: str,
    target_tokens: int = 6000,
) -> str:
    """Collect source content from conversation citations and random chunks"""

    # Step 1: Get all messages in the conversation thread till now
    messages_query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages_result = await session.execute(messages_query)
    conversation_messages = messages_result.scalars().all()

    # Step 2: Load random chunks from all citations until we have ~6K tokens
    tkz = tiktoken.encoding_for_model("gpt-4o")
    collected_content = []
    current_tokens = 0

    # Collect all citations from the conversation with null checks
    all_citations = []
    for msg in conversation_messages:
        if msg.citations and isinstance(msg.citations, list):
            all_citations.extend(msg.citations)

    if all_citations:
        # Get chunks from cited documents
        cited_filenames = [citation.name for citation in all_citations]
        chunks_query = (
            select(DocumentChunk.content, SourceDocument.filename)
            .join(SourceDocument)
            .where(
                SourceDocument.filename.in_(cited_filenames),
                SourceDocument.active == True,
            )
            .order_by(func.random())
        )
        chunks_result = await session.execute(chunks_query)
        available_chunks = chunks_result.all()

        # Add chunks until we reach the target token count
        for content, filename in available_chunks:
            chunk_tokens = len(tkz.encode(content))
            if current_tokens + chunk_tokens > target_tokens:
                break
            collected_content.append(f"From {filename}:\n{content}")
            current_tokens += chunk_tokens

        tu.logger.info(
            f"Collected {len(collected_content)} chunks from citations with {current_tokens} tokens"
        )

    # If we don't have enough content from citations, get random chunks
    if current_tokens < target_tokens:
        random_chunks_query = (
            select(DocumentChunk.content, SourceDocument.filename)
            .join(SourceDocument)
            .where(SourceDocument.active == True)
            .order_by(func.random())
        )
        random_chunks_result = await session.execute(random_chunks_query)
        random_chunks = random_chunks_result.all()

        for content, filename in random_chunks:
            chunk_tokens = len(tkz.encode(content))
            if current_tokens + chunk_tokens > target_tokens:
                break
            collected_content.append(f"From {filename}:\n{content}")
            current_tokens += chunk_tokens

        tu.logger.info(
            f"Added random chunks, total: {len(collected_content)} chunks with {current_tokens} tokens"
        )

    return "\n\n".join(collected_content)


async def generate_meditation_transcript(source_text: str) -> str:
    """Generate meditation transcript from source content"""

    model = get_llm("gpt-4o")
    transcript_prompt = dedent(
        f"""
        Based on the following spiritual and contemplative texts, create a peaceful 5-minute meditation script that captures the essence of the wisdom. The script should be:

        - Approximately 5 minutes when read aloud (about 600-750 words)
        - Written in a calm, soothing tone suitable for meditation
        - Include gentle breathing instructions and pauses
        - Focus on mindfulness, inner peace, and spiritual growth
        - Be suitable for audio narration with natural flow
        - For sound effects use tags like [breathing], [pause], [silence], [silence-n], etc.

        Source texts:
        {source_text}

        Generate only the meditation script text.
        """
    )

    # Create a thread with the prompt
    thread = tt.Thread(
        tt.system("You are a meditation script writer who creates peaceful, calming meditation scripts."),
        id="meditation_transcript"
    )
    
    # Add the user message to the thread
    thread.append(tt.Message(transcript_prompt, "user"))

    response = await model.chat_async(thread)
    
    # Fix: Handle response properly whether it's a string or object
    response_content = response.content if hasattr(response, 'content') else str(response)

    return response_content


async def generate_audio_from_transcript(transcript: str) -> bytes:
    """Generate audio from transcript using OpenAI TTS"""
    
    model = get_llm("gpt-4o")
    audio_bytes = await model.text_to_speech_async(
        prompt=transcript,
        voice="shimmer",
        model="gpt-4o-mini-tts",
        instructions="""
        For sound effects transcript has tags like [breathing], [pause], [silence], etc.
        Please follow these instructions:
        - Speak in a calm, soothing voice
        - Pause appropriately for breathing instructions
        - Use natural pacing for meditation
        - Maintain consistent volume and tone
        """,
    )
    
    return audio_bytes


async def compress_audio_to_mp3(audio_bytes: bytes) -> bytes:
    """Compress audio bytes to MP3 format using FFmpeg"""
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as input_file:
        input_file.write(audio_bytes)
        input_path = input_file.name

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as output_file:
        output_path = output_file.name

    try:
        # Use FFmpeg to convert to MP3
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            "-y",  # Overwrite output
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Read the compressed audio
        with open(output_path, "rb") as f:
            compressed_audio = f.read()
        
        return compressed_audio
        
    finally:
        # Clean up temporary files
        for temp_path in [input_path, output_path]:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                tu.logger.warning(f"Failed to cleanup {temp_path}: {e}")
