import asyncio
import tempfile
import os
import subprocess
import random
from typing import Tuple
from PIL import Image
import pickle
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from supabase import Client
from tuneapi import tu

from src.db import Conversation
from src.content.image import _generate_image, CONTEMPLATION_PROMPTS
from src.content.audio import (
    collect_source_content_optimized,
    generate_meditation_transcript_optimized,
    generate_audio_from_transcript_optimized,
)
from src.utils.profiler import profile_operation, print_profiler_summary
from src.settings import get_supabase_client

# Cache for image generation with persistent storage
_image_cache = {}
_cache_file = Path("image_cache.pkl")

def _load_image_cache():
    """Load image cache from disk"""
    global _image_cache
    try:
        if _cache_file.exists():
            with open(_cache_file, 'rb') as f:
                _image_cache = pickle.load(f)
                tu.logger.info(f"Loaded {len(_image_cache)} cached images from disk")
    except Exception as e:
        tu.logger.error(f"Failed to load image cache: {e}")
        _image_cache = {}

def _save_image_cache():
    """Save image cache to disk"""
    try:
        with open(_cache_file, 'wb') as f:
            pickle.dump(_image_cache, f)
    except Exception as e:
        tu.logger.error(f"Failed to save image cache: {e}")

# Load cache on module import
_load_image_cache()

# Pre-generate these common meditation images for faster video generation
COMMON_MEDITATION_PROMPTS = [
    "Peaceful zen garden with flowing water and soft sunlight",
    "Serene mountain lake at sunset with gentle ripples", 
    "Tranquil forest clearing with dappled morning light",
    "Misty mountains with flowing clouds at dawn",
    "Peaceful bamboo grove with soft filtered light",
    "Quiet temple garden with stone lanterns and cherry blossoms",
    "Serene pond with lotus flowers and reflections",
    "Calm desert dunes under a twilight sky",
    "Peaceful meadow with wildflowers and gentle breeze",
    "Soft morning light filtering through bamboo leaves"
]

def _get_image_cache_key(prompt: str) -> str:
    """Generate cache key for image prompt"""
    return str(hash(prompt) % 10000)  # Use string for better pickle compatibility

async def pre_generate_common_images():
    """Pre-generate common meditation images for faster video generation"""
    tu.logger.info("Pre-generating common meditation images...")
    generated_count = 0
    
    for prompt in COMMON_MEDITATION_PROMPTS:
        cache_key = _get_image_cache_key(prompt)
        if cache_key not in _image_cache:
            try:
                tu.logger.info(f"Pre-generating image for: {prompt[:50]}...")
                image = await _generate_image(prompt)
                _image_cache[cache_key] = image
                generated_count += 1
                tu.logger.info(f"Cached image for prompt: {prompt[:50]}")
                
                # Save cache after each image to prevent loss
                _save_image_cache()
                
            except Exception as e:
                tu.logger.error(f"Failed to pre-generate image for {prompt[:50]}: {e}")
    
    tu.logger.info(f"Pre-generation complete. Generated {generated_count} new images. Total cached: {len(_image_cache)}")

async def generate_and_cache_image(prompt: str):
    """Generate image and cache it for future use"""
    cache_key = _get_image_cache_key(prompt)
    
    if cache_key in _image_cache:
        tu.logger.info(f"Using cached image for: {prompt[:50]}")
        return _image_cache[cache_key]
    
    tu.logger.info(f"Generating new image for: {prompt[:50]}")
    image = await _generate_image(prompt)
    _image_cache[cache_key] = image
    
    # Save cache after generating new image
    _save_image_cache()
    
    return image

class ParallelVideoGenerator:
    def __init__(self):
        self.spb_client = get_supabase_client()

    async def generate_video_parallel_optimized(
        self,
        session: AsyncSession,
        conversation_id: str,
        message_id: str,
        content_id: str,
    ) -> Tuple[str, str]:
        """Generate video content with maximum parallelization and caching"""
        
        request_id = f"video_{content_id}_{int(tu.SimplerTimes.get_now_fp64())}"
        
        # Step 1: Load conversation first (sequential to avoid session conflicts)
        async with profile_operation("conversation_load", request_id) as op:
            conversation = await self._load_conversation(session, conversation_id)
            op.finish()
        
        # Step 2: Generate source content (sequential)
        async with profile_operation("source_content_generation") as op:
            source_content = await self._generate_source_content(session, conversation_id)
            op.finish(source_length=len(source_content))
        
        # Step 3: Generate image prompt and transcript in parallel (no DB operations)
        async with profile_operation("parallel_transcript_and_image") as op:
            image_prompt = await self._generate_image_prompt_cached()
            transcript_task = self._generate_transcript_optimized(source_content)
            image_task = self._generate_image_cached(image_prompt)
            
            transcript, pil_image = await asyncio.gather(transcript_task, image_task)
            op.finish(transcript_length=len(transcript), image_size=pil_image.size)
        
        # Step 4: Generate audio first, then create video (sequential dependency)
        async with profile_operation("audio_generation") as op:
            audio_bytes = await self._generate_audio_optimized(transcript)
            op.finish(audio_size_bytes=len(audio_bytes))
        
        # Step 5: Create video using the audio
        async with profile_operation("video_creation") as op:
            video_path = await self._create_video_ultra_optimized(pil_image, audio_bytes)
            op.finish(video_path=video_path)
        
        # Step 6: Upload video
        async with profile_operation("video_upload") as op:
            content_path = await self._upload_video_optimized(video_path, content_id)
            op.finish(upload_path=content_path)
        
        print_profiler_summary()
        return content_path, transcript

    async def _load_conversation(self, session: AsyncSession, conversation_id: str):
        """Load conversation efficiently"""
        query = select(Conversation).where(Conversation.id == conversation_id)
        result = await session.execute(query)
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            raise ValueError("Conversation not found")
        return conversation

    async def _generate_source_content(
        self, session: AsyncSession, conversation_id: str
    ) -> str:
        """Generate source content for transcript"""
        return await collect_source_content_optimized(session, conversation_id)

    async def _generate_image_prompt_cached(self) -> str:
        """Generate image prompt with preference for cached common prompts"""
        import random
        
        # 70% chance to use a common cached prompt for speed
        if random.random() < 0.7 and COMMON_MEDITATION_PROMPTS:
            return random.choice(COMMON_MEDITATION_PROMPTS)
        
        # 30% chance to use original variety from CONTEMPLATION_PROMPTS
        return random.choice(CONTEMPLATION_PROMPTS)

    async def _generate_transcript_optimized(self, source_content: str) -> str:
        """Generate meditation transcript with optimization"""
        return await generate_meditation_transcript_optimized(source_content)

    async def _generate_image_cached(self, prompt: str) -> Image.Image:
        """Generate image with persistent caching"""
        return await generate_and_cache_image(prompt)

    async def _generate_audio_optimized(self, transcript: str) -> bytes:
        """Generate audio with optimization"""
        return await generate_audio_from_transcript_optimized(transcript)

    async def _create_video_ultra_optimized(
        self, pil_image: Image.Image, audio_bytes: bytes
    ) -> str:
        """Create video with ultra-optimized FFmpeg settings"""
        
        # Create temporary files with optimized settings
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as img_file:
            # Use JPEG instead of PNG for faster processing
            pil_image.save(img_file.name, "JPEG", quality=85, optimize=True)
            image_path = img_file.name

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as audio_file:
            audio_file.write(audio_bytes)
            audio_path = audio_file.name

        # Create output video path
        video_path = tempfile.mktemp(suffix=".mp4")

        try:
            # Ultra-optimized FFmpeg command for maximum speed
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output
                "-loop", "1",  # Loop image
                "-i", image_path,  # Input image
                "-i", audio_path,  # Input audio
                "-c:v", "libx264",  # Video codec
                "-preset", "superfast",  # Even faster than ultrafast
                "-crf", "30",  # Lower quality for faster encoding (was 28)
                "-c:a", "aac",  # Audio codec
                "-b:a", "64k",  # Lower audio bitrate for speed (was 96k)
                "-vf", "scale=720:480",  # Lower resolution for speed
                "-r", "15",  # Lower frame rate for speed
                "-shortest",  # End when shortest input ends
                "-pix_fmt", "yuv420p",  # Pixel format
                "-movflags", "+faststart",  # Web optimization
                "-threads", "0",  # Use all available threads
                video_path,
            ]

            # Add hardware acceleration if available
            try:
                # Check for hardware acceleration
                test_cmd = ["ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "testsrc2", "-t", "1", "-f", "null", "-"]
                subprocess.run(test_cmd, capture_output=True, timeout=5)
                # If successful, use hardware acceleration
                cmd.insert(1, "-hwaccel")
                cmd.insert(2, "auto")
            except:
                pass  # Use software encoding

            # Run FFmpeg with timeout
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg failed: {result.stderr}")

            return video_path

        finally:
            # Cleanup temporary files
            for temp_path in [image_path, audio_path]:
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except:
                    pass

    async def _upload_video_optimized(self, video_path: str, content_id: str) -> str:
        """Upload video with optimized settings"""
        try:
            with open(video_path, "rb") as f:
                video_data = f.read()

            # Use optimized upload path
            content_path = f"meditation-videos/{content_id}.mp4"
            
            # Upload with correct signature
            self.spb_client.storage.from_("generations").upload(
                content_path,
                video_data,
                {"content-type": "video/mp4"}
            )

            return content_path

        finally:
            # Cleanup video file
            try:
                os.unlink(video_path)
            except:
                pass

    # Legacy methods for backward compatibility
    async def _generate_image_prompt(self) -> str:
        """Generate image prompt"""
        return random.choice(CONTEMPLATION_PROMPTS)

    async def _generate_transcript(self, source_content: str) -> str:
        """Generate meditation transcript"""
        return await generate_meditation_transcript_optimized(source_content)

    async def _generate_image(self, prompt: str) -> Image.Image:
        """Generate image"""
        return await _generate_image(prompt)

    async def _generate_audio(self, transcript: str) -> bytes:
        """Generate audio from transcript"""
        return await generate_audio_from_transcript_optimized(transcript)

    async def _create_video_optimized(
        self, pil_image: Image.Image, audio_bytes: bytes
    ) -> str:
        """Create video with optimized FFmpeg settings"""
        return await self._create_video_ultra_optimized(pil_image, audio_bytes)

    async def _upload_video(self, video_path: str) -> str:
        """Upload video to Supabase"""
        return await self._upload_video_optimized(video_path, "temp")

# Global instance
parallel_generator = ParallelVideoGenerator() 