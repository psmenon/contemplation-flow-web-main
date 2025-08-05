import asyncio
import tempfile
import os
import random
import subprocess
from typing import Tuple
from PIL import Image

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
from src.content.audio import (
    collect_source_content_optimized,  # ✅ Changed to optimized version
    generate_meditation_transcript,
    generate_audio_from_transcript,
)
from src.utils.profiler import profile_operation, get_profiler, print_profiler_summary


class ParallelVideoGenerator:
    def __init__(self):
        self.model = get_llm("gpt-4o")
        self.spb_client = get_supabase_client()

    async def generate_video_parallel(
        self,
        session: AsyncSession,
        conversation_id: str,
        message_id: str,
        content_id: str,
    ) -> Tuple[str, str]:
        """Generate video content using parallel processing - PROFILED"""
        
        request_id = f"video_{content_id}_{int(tu.SimplerTimes.get_now_fp64())}"
        
        async with profile_operation("conversation_load", request_id) as op:
            query = select(Conversation).where(Conversation.id == conversation_id)
            result = await session.execute(query)
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                raise ValueError("Conversation not found")
            op.finish()
        
        async with profile_operation("parallel_source_and_image") as op:
            # Start parallel tasks
            tasks = [
                self._generate_source_content(session, conversation_id),
                self._generate_image_prompt(),
            ]
            
            # Wait for source content and image prompt
            source_content, image_prompt = await asyncio.gather(*tasks)
            op.finish(source_length=len(source_content), image_prompt=image_prompt)
        
        async with profile_operation("parallel_transcript_and_image") as op:
            # Start parallel generation tasks
            generation_tasks = [
                self._generate_transcript(source_content),
                self._generate_image(image_prompt),
            ]
            
            # Wait for both transcript and image
            transcript, pil_image = await asyncio.gather(*generation_tasks)
            op.finish(transcript_length=len(transcript), image_size=pil_image.size)
        
        async with profile_operation("audio_generation") as op:
            # Generate audio from transcript
            audio_bytes = await self._generate_audio(transcript)
            op.finish(audio_size_bytes=len(audio_bytes))
        
        async with profile_operation("video_creation") as op:
            # Create video with optimized FFmpeg
            video_path = await self._create_video_optimized(pil_image, audio_bytes)
            op.finish(video_path=video_path)
        
        async with profile_operation("supabase_upload") as op:
            # Upload to Supabase
            content_path = await self._upload_video(video_path)
            op.finish(upload_path=content_path)
        
        print_profiler_summary()
        return content_path, transcript

    async def _generate_source_content(
        self, session: AsyncSession, conversation_id: str
    ) -> str:
        """Generate source content for transcript"""
        return await collect_source_content_optimized(session, conversation_id)  # ✅ Changed to optimized

    async def _generate_image_prompt(self) -> str:
        """Generate image prompt"""
        return random.choice(CONTEMPLATION_PROMPTS)

    async def _generate_transcript(self, source_content: str) -> str:
        """Generate meditation transcript"""
        return await generate_meditation_transcript(source_content)

    async def _generate_image(self, prompt: str) -> Image.Image:
        """Generate image"""
        return await _generate_image(prompt)

    async def _generate_audio(self, transcript: str) -> bytes:
        """Generate audio from transcript"""
        return await generate_audio_from_transcript(transcript)

    async def _create_video_optimized(
        self, pil_image: Image.Image, audio_bytes: bytes
    ) -> str:
        """Create video with optimized FFmpeg settings"""
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img_file:
            pil_image.save(img_file.name, "PNG")
            image_path = img_file.name

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as audio_file:
            audio_file.write(audio_bytes)
            audio_path = audio_file.name

        # Create output video path
        video_path = tempfile.mktemp(suffix=".mp4")

        try:
            # Optimized FFmpeg command with hardware acceleration
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output
                "-loop", "1",  # Loop image
                "-i", image_path,  # Input image
                "-i", audio_path,  # Input audio
                "-c:v", "libx264",  # Video codec
                "-preset", "ultrafast",  # Fast encoding
                "-crf", "23",  # Quality setting
                "-c:a", "aac",  # Audio codec
                "-b:a", "128k",  # Audio bitrate
                "-shortest",  # End when shortest input ends
                "-pix_fmt", "yuv420p",  # Pixel format
                video_path,
            ]

            # Check for hardware acceleration
            try:
                subprocess.run(["ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "testsrc2", "-t", "1", "-f", "null", "-"], capture_output=True)
                # If successful, use hardware acceleration
                cmd[1:1] = ["-hwaccel", "auto"]
            except:
                pass  # Use software encoding

            # Run FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg failed: {result.stderr}")

            return video_path

        finally:
            # Cleanup temporary files
            try:
                os.unlink(image_path)
                os.unlink(audio_path)
            except:
                pass

    async def _upload_video(self, video_path: str) -> str:
        """Upload video to Supabase"""
        try:
            with open(video_path, "rb") as f:
                video_data = f.read()

            # Upload to Supabase
            file_name = f"video_{tu.SimplerTimes.get_now_fp64()}.mp4"
            response = self.spb_client.storage.from_("content-files").upload(
                file_name, video_data
            )

            # Get public URL
            content_path = self.spb_client.storage.from_("content-files").get_public_url(
                file_name
            )

            return content_path

        finally:
            # Cleanup video file
            try:
                os.unlink(video_path)
            except:
                pass


# Global instance
parallel_generator = ParallelVideoGenerator() 