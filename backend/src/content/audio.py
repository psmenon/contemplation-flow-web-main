import tempfile
import os
import subprocess
from textwrap import dedent
import tiktoken

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from supabase import Client
from tuneapi import tu

from src.db import (
    ContentGeneration,
    ContentType,
    Conversation,
    Message,
    SourceDocument,
    DocumentChunk,
)
from src.settings import get_llm, get_supabase_client
from src.db import get_db_session


async def generate_audio_content(
    content_id: str,
    conversation_id: str,
    message_id: str,
) -> None:
    """Background task to generate audio content and update the database record"""

    # Create a new database session for the background task
    session = get_db_session()
    spb_client = get_supabase_client()

    try:
        tu.logger.info(f"Starting background audio generation for content {content_id}")

        # Generate the audio content
        content_path, transcript = await generate_audio_sync(
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

    except Exception as e:
        tu.logger.error(
            f"Error in background audio generation for content {content_id}: {e}"
        )
        # Could optionally update the record with an error status here
    finally:
        await session.close()


async def generate_audio_sync(
    session: AsyncSession,
    conversation_id: str,
    message_id: str,
    spb_client: Client,
    content_id: str,
) -> tuple[str, str]:
    """Generate audio content synchronously and return content_path and transcript"""

    # Get the conversation to get the user_id
    query = select(Conversation).where(Conversation.id == conversation_id)
    result = await session.execute(query)
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise ValueError(f"Conversation with id {conversation_id} not found")

    tu.logger.info(f"Generating audio for conversation {conversation_id}/{message_id}")

    # Get source content and generate transcript
    source_content = await collect_source_content(session, conversation_id)
    transcript = await generate_meditation_transcript(source_content)

    # Generate audio using text_to_speech_async
    model = get_llm("gpt-4o")
    audio_bytes = await model.text_to_speech_async(
        prompt=transcript,
        voice="shimmer",
        model="gpt-4o-mini-tts",
        instructions="""
        For sound effects transcript has tags like [breathing], [pause], [silence], etc.
        - For pauses use [pause] tag.
        - For breathing use [breathing] tag.
        - When has [silence], add 1 second of silence.
        - When has [silence-n], add n seconds of silence.
        """,
    )
    tu.logger.info(f"Generated audio of {len(audio_bytes)} bytes")

    # Compress audio to mp3 using ffmpeg
    compressed_audio_bytes = await compress_audio_to_mp3(audio_bytes)
    tu.logger.info(f"Compressed audio to {len(compressed_audio_bytes)} bytes")

    # Upload to Supabase
    content_path = f"meditation-audio/{content_id}.mp3"

    tu.logger.info(f"Uploading audio to supabase: {content_path}")
    spb_client.storage.from_("generations").upload(
        content_path,
        compressed_audio_bytes,
        {"content-type": "audio/mpeg"},
    )

    tu.logger.info(f"Successfully created audio content generation: {content_id}")
    return content_path, transcript


async def compress_audio_to_mp3(audio_bytes: bytes) -> bytes:
    """Compress audio bytes to MP3 format using ffmpeg"""

    # Create temporary files for input and output
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as input_file:
        input_file.write(audio_bytes)
        input_path = input_file.name

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as output_file:
        output_path = output_file.name

    try:
        # Use ffmpeg to convert to MP3 with good quality settings
        cmd = [
            "ffmpeg",
            "-i",
            input_path,  # Input file
            "-codec:a",
            "libmp3lame",  # MP3 encoder
            "-b:a",
            "128k",  # Audio bitrate (128 kbps for good quality/size balance)
            "-ar",
            "44100",  # Sample rate
            "-ac",
            "2",  # Stereo channels
            "-y",  # Overwrite output file
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        tu.logger.info(f"Successfully compressed audio using ffmpeg")

        # Read the compressed audio
        with open(output_path, "rb") as f:
            compressed_bytes = f.read()

        return compressed_bytes

    except subprocess.CalledProcessError as e:
        tu.logger.error(f"FFmpeg compression failed: {e}")
        tu.logger.error(f"FFmpeg stderr: {e.stderr}")
        # If compression fails, return original audio bytes
        tu.logger.warning("Falling back to original audio without compression")
        return audio_bytes

    finally:
        # Clean up temporary files
        for temp_path in [input_path, output_path]:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                tu.logger.warning(f"Failed to cleanup temporary file {temp_path}: {e}")


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

    # Collect all citations from the conversation
    all_citations = []
    for msg in conversation_messages:
        if msg.citations:
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

    transcript = await model.chat_async(transcript_prompt)
    transcript = transcript.strip()
    tu.logger.info(f"Generated transcript of length: {len(transcript)} characters")
    return transcript


async def generate_audio_from_transcript(transcript: str) -> bytes:
    """Generate audio bytes from meditation transcript"""

    model = get_llm("gpt-4o")
    audio_bytes = await model.text_to_speech_async(
        prompt=transcript,
        voice="shimmer",
        model="gpt-4o-mini-tts",
        instructions="""
        For sound effects transcript has tags like [breathing], [pause], [silence], etc.
        - For pauses use [pause] tag.
        - For breathing use [breathing] tag.
        - When has [silence], add 1 second of silence.
        - When has [silence-n], add n seconds of silence.
        """,
    )
    tu.logger.info(f"Generated audio of {len(audio_bytes)} bytes")
    return audio_bytes
