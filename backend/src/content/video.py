import subprocess
import tempfile
import os
import random
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from supabase import Client
from tuneapi import tu

from src.db import (
    ContentGeneration,
    Conversation,
)
from src.content.image import _generate_image, CONTEMPLATION_PROMPTS
from src.settings import get_supabase_client, get_llm
from src.db import get_db_session
from src.content.audio import (
    collect_source_content,
    generate_meditation_transcript,
    generate_audio_from_transcript,
)
from src.content.parallel_video import parallel_generator


async def generate_video_content(
    content_id: str,
    conversation_id: str,
    message_id: str,
) -> None:
    """Background task to generate video content and update the database record"""

    # Create a new database session for the background task
    session = get_db_session()
    spb_client = get_supabase_client()

    try:
        tu.logger.info(f"Starting background video generation for content {content_id}")

        # Generate the video content using parallel processing
        content_path, transcript = await generate_video_parallel(
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
                f"Successfully completed video generation for content {content_id}"
            )
        else:
            tu.logger.error(f"ContentGeneration record not found for id {content_id}")

    except Exception as e:
        tu.logger.error(
            f"Error in background video generation for content {content_id}: {e}"
        )
        # Could optionally update the record with an error status here
    finally:
        await session.close()


async def generate_video_parallel(
    session: AsyncSession,
    conversation_id: str,
    message_id: str,
    spb_client: Client,
    content_id: str,
) -> tuple[str, str]:
    """Generate video content with parallel processing for maximum speed"""
    
    tu.logger.info(f"Starting parallel video generation for {content_id}")
    
    # Step 1: Get conversation and start source content collection
    query = select(Conversation).where(Conversation.id == conversation_id)
    result = await session.execute(query)
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise ValueError(f"Conversation with id {conversation_id} not found")

    # Step 2: Start source content collection and image generation in parallel
    source_content_task = collect_source_content(session, conversation_id)
    image_task = _generate_image_parallel()
    
    # Step 3: Wait for source content, then start transcript generation
    source_content = await source_content_task
    transcript_task = generate_meditation_transcript(source_content)
    
    # Step 4: Wait for transcript, then start audio generation
    transcript = await transcript_task
    audio_task = generate_audio_from_transcript(transcript)
    
    # Step 5: Wait for image and audio to complete in parallel
    image, audio_bytes = await asyncio.gather(
        image_task,
        audio_task,
        return_exceptions=True
    )
    
    # Handle exceptions
    if isinstance(image, Exception):
        tu.logger.error(f"Image generation failed: {image}")
        raise image
    if isinstance(audio_bytes, Exception):
        tu.logger.error(f"Audio generation failed: {audio_bytes}")
        raise audio_bytes
    
    # Step 6: Create video with optimized FFmpeg
    video_path = await _create_video_optimized(image, audio_bytes)
    
    # Step 7: Upload to Supabase
    content_path = f"meditation-videos/{content_id}.mp4"
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    
    tu.logger.info(f"Uploading video to supabase: {content_path}")
    spb_client.storage.from_("generations").upload(
        content_path,
        video_bytes,
        {"content-type": "video/mp4"},
    )
    
    # Cleanup
    try:
        os.unlink(video_path)
    except Exception as e:
        tu.logger.warning(f"Failed to cleanup video temp file: {e}")
    
    tu.logger.info(f"Successfully completed parallel video generation: {content_id}")
    return content_path, transcript


async def _generate_image_parallel():
    """Generate image with optimized settings for speed"""
    model = get_llm("gpt-4o")
    prompt = random.choice(CONTEMPLATION_PROMPTS)
    
    tu.logger.info(f"Generating image with prompt: {prompt}")
    img_gen_response = await model.image_gen_async(
        prompt=prompt,
        n=1,
        size="1024x1024",  # Smaller size for faster generation
        quality="standard",
    )
    
    tu.logger.info(f"Generated image: {img_gen_response.image.size}")
    return img_gen_response.image


async def _create_video_optimized(
    image,
    audio_bytes: bytes,
) -> str:
    """Create video with optimized FFmpeg settings"""
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img_file:
        image.save(img_file.name, "PNG")
        image_path = img_file.name

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as audio_file:
        audio_file.write(audio_bytes)
        audio_path = audio_file.name

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as video_file:
        video_path = video_file.name

    try:
        # Optimized FFmpeg command
        success = _create_video_ffmpeg_optimized(
            image_path, audio_path, video_path
        )
        if not success:
            raise Exception("FFmpeg video creation failed")
        
        return video_path
        
    finally:
        # Cleanup temp files
        for temp_path in [image_path, audio_path]:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                tu.logger.warning(f"Failed to cleanup {temp_path}: {e}")


def _create_video_ffmpeg_optimized(
    image_path: str,
    audio_path: str,
    output_path: str,
) -> bool:
    """Optimized FFmpeg command for faster video creation"""
    
    # Check for hardware acceleration
    hw_accel = "-hwaccel auto" if _check_hardware_acceleration() else ""
    
    # Optimized settings for faster encoding
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        hw_accel,
        "-loop", "1",  # Loop image
        "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",  # Video codec
        "-preset", "ultrafast",  # Fastest encoding
        "-crf", "23",  # Good quality
        "-c:a", "aac",  # Audio codec
        "-b:a", "128k",  # Audio bitrate
        "-shortest",  # End when audio ends
        "-movflags", "+faststart",  # Web optimization
        output_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        tu.logger.error("FFmpeg timeout")
        return False
    except Exception as e:
        tu.logger.error(f"FFmpeg error: {e}")
        return False


def _check_hardware_acceleration() -> bool:
    """Check if hardware acceleration is available"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "testsrc", "-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False


async def generate_video_sync(
    session: AsyncSession,
    conversation_id: str,
    message_id: str,
    spb_client: Client,
    content_id: str,
) -> tuple[str, str]:
    """Generate video content using parallel processing"""
    
    # Use the parallel generator instead of sequential processing
    content_path, transcript = await parallel_generator.generate_video_parallel(
        session, conversation_id, message_id, content_id
    )
    
    return content_path, transcript


def create_video_ffmpeg(
    image_path: str,
    audio_path: str,
    output_path: str,
):
    """
    Create video from image and audio using FFmpeg (legacy method)
    """
    cmd = [
        "ffmpeg",
        "-loop",
        "1",  # Loop the image
        "-i",
        image_path,  # Input image
        "-i",
        audio_path,  # Input audio
        "-c:v",
        "libx264",  # Video codec
        "-tune",
        "stillimage",  # Optimize for still images
        "-c:a",
        "aac",  # Audio codec
        "-b:a",
        "192k",  # Audio bitrate
        "-pix_fmt",
        "yuv420p",  # Pixel format for compatibility
        "-shortest",  # Stop when shortest input ends
        "-y",  # Overwrite output file
        output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Video created successfully: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        print(f"FFmpeg output: {e.stderr}")
        return False