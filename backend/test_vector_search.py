#!/usr/bin/env python3
"""
Test script to verify vector search and citations work with populated source documents
"""

import asyncio
import sys
from tuneapi import tu

# Add the backend directory to the path
sys.path.append(tu.folder(__file__))

from src.settings import get_llm, get_supabase_client
from src.db import get_db_session, DocumentChunk, SourceDocument
from sqlalchemy import select
from sqlalchemy.orm import selectinload


async def test_vector_search():
    """Test vector search with populated documents"""
    
    print("🔍 Testing Vector Search with Populated Documents")
    print("=" * 50)
    
    # 1. Check if we have source documents
    session = get_db_session(sync=False)
    try:
        # Count source documents
        query = select(SourceDocument).where(SourceDocument.active == True)
        result = await session.execute(query)
        source_docs = result.scalars().all()
        
        print(f"📚 Found {len(source_docs)} active source documents:")
        for doc in source_docs:
            print(f"  - {doc.filename} ({doc.file_size_bytes} bytes, status: {doc.status.value})")
        
        if not source_docs:
            print("❌ No active source documents found!")
            return
        
        # 2. Count document chunks
        query = select(DocumentChunk).options(selectinload(DocumentChunk.source_document))
        result = await session.execute(query)
        chunks = result.scalars().all()
        
        print(f"\n📄 Found {len(chunks)} document chunks:")
        for chunk in chunks[:5]:  # Show first 5
            print(f"  - From {chunk.source_document.filename}: {chunk.content[:100]}...")
        
        if len(chunks) > 5:
            print(f"  ... and {len(chunks) - 5} more chunks")
        
        # 3. Test vector search
        print(f"\n🔍 Testing vector search...")
        model = get_llm("gpt-4o")
        
        # Test query
        test_query = "What are the spiritual teachings about meditation?"
        print(f"Query: '{test_query}'")
        
        # Generate embedding
        embedding_response = await model.embedding_async(
            test_query, model="text-embedding-3-small"
        )
        embedding = embedding_response.embedding[0]
        print(f"Generated embedding: {len(embedding)} dimensions")
        
        # Search for similar chunks
        from sqlalchemy import func
        query = (
            select(DocumentChunk.content, SourceDocument.filename)
            .join(SourceDocument)
            .where(SourceDocument.active == True)
            .order_by(DocumentChunk.embedding.max_inner_product(embedding))
            .limit(3)
        )
        
        result = await session.execute(query)
        search_results = result.all()
        
        print(f"\n🎯 Top 3 most relevant chunks:")
        for i, (content, filename) in enumerate(search_results, 1):
            print(f"\n{i}. From: {filename}")
            print(f"   Content: {content[:200]}...")
        
        # 4. Test citation generation
        print(f"\n📖 Generating citations...")
        from src import wire
        from src.settings import get_supabase_client
        from src.services.chat import generate_citation_url
        
        spb_client = get_supabase_client()
        
        citations = [
            wire.CitationInfo(
                name=filename, 
                url=generate_citation_url(filename, spb_client)
            )
            for _, filename in search_results
        ]
        
        print(f"Generated {len(citations)} citations:")
        for i, citation in enumerate(citations, 1):
            print(f"  {i}. {citation.name} -> {citation.url}")
        
        print(f"\n✅ Vector search and citations are working!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(test_vector_search()) 