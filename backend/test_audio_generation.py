#!/usr/bin/env python3
"""
Test script to check if audio generation is working
"""

import asyncio
import sys
from tuneapi import tu

# Add the backend directory to the path
sys.path.append(tu.folder(__file__))

from src.content.audio import generate_meditation_transcript, generate_audio_from_transcript
from src.settings import get_llm


async def test_audio_generation():
    """Test audio generation components"""
    
    print("🎵 Testing Audio Generation Components")
    print("=" * 40)
    
    try:
        # Test 1: Transcript Generation
        print("\n1. Testing transcript generation...")
        test_source = "Meditation is a practice of focusing the mind and finding inner peace. The ancient texts teach us to observe our thoughts without judgment."
        
        transcript = await generate_meditation_transcript(test_source)
        print(f"✅ Transcript generated: {len(transcript)} characters")
        print(f"   Preview: {transcript[:200]}...")
        
        # Test 2: Audio Generation
        print("\n2. Testing audio generation...")
        audio_bytes = await generate_audio_from_transcript(transcript)
        print(f"✅ Audio generated: {len(audio_bytes)} bytes")
        
        print("\n🎉 Audio generation is working!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_audio_generation()) 