#!/usr/bin/env python3
"""
Test script to verify audio content retrieval and serving
"""

import asyncio
import sys
from tuneapi import tu

# Add the backend directory to the path
sys.path.append(tu.folder(__file__))

from src.db import get_db_session, ContentGeneration, ContentType
from src.services.content import get_content
from src.settings import get_supabase_client
from sqlalchemy import select
from uuid import UUID


async def test_audio_retrieval():
    """Test audio content retrieval"""
    
    print("🔍 Testing Audio Content Retrieval")
    print("=" * 40)
    
    session = get_db_session()
    spb_client = get_supabase_client()
    
    try:
        # Get a completed audio generation
        query = (
            select(ContentGeneration)
            .where(
                ContentGeneration.content_type == ContentType.AUDIO,
                ContentGeneration.content_path.isnot(None)
            )
            .order_by(ContentGeneration.created_at.desc())
            .limit(1)
        )
        
        result = await session.execute(query)
        audio_gen = result.scalar_one_or_none()
        
        if not audio_gen:
            print("❌ No completed audio generations found")
            return
        
        print(f"✅ Found audio generation: {audio_gen.id}")
        print(f"   Path: {audio_gen.content_path}")
        print(f"   Transcript: {len(audio_gen.transcript) if audio_gen.transcript else 0} chars")
        
        # Test the get_content function
        print("\n🧪 Testing get_content function...")
        
        # Mock a user (you'll need to replace with a real user ID)
        from src.db import UserProfile
        mock_user = UserProfile(id="test-user-id")
        
        try:
            content_response = await get_content(
                str(audio_gen.id),
                mock_user,
                session,
                spb_client
            )
            
            print(f"✅ Content response status: {content_response.status}")
            if hasattr(content_response, 'content_url') and content_response.content_url:
                print(f"✅ Content URL: {content_response.content_url}")
            else:
                print("❌ No content URL in response")
                
        except Exception as e:
            print(f"❌ Error testing get_content: {e}")
            
        # Test Supabase storage directly
        print("\n🧪 Testing Supabase storage directly...")
        try:
            # Try to get a signed URL
            presigned_response = spb_client.storage.from_("generations").create_signed_url(
                audio_gen.content_path, 3600
            )
            
            if presigned_response.get("error"):
                print(f"❌ Supabase error: {presigned_response.get('error')}")
            else:
                print(f"✅ Supabase signed URL: {presigned_response.get('signedURL')}")
                
        except Exception as e:
            print(f"❌ Error with Supabase: {e}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(test_audio_retrieval()) 