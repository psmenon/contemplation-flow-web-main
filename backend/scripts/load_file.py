import sys
from tuneapi import tu

sys.path.append(tu.folder(tu.folder(__file__)))

import os
import aiofiles
import asyncio
from fire import Fire

from src.settings import get_llm
from src.chunking import extract_pdf_text, extract_docx_text
from src.db import get_db_session, SourceDocument, DocumentChunk, DocumentStatus
from src.settings import get_supabase_client


async def _main(fp: str):
    tu.logger.info(f">>>> Loading file: {fp}")
    is_pdf = fp.endswith(".pdf")
    is_docx = fp.endswith(".docx")
    if not is_pdf and not is_docx:
        raise ValueError(f"Unsupported file type: {fp}")

    # Get file info
    filename = os.path.basename(fp)
    file_size = os.path.getsize(fp)

    async with aiofiles.open(fp, "rb") as f:
        content = await f.read()
        if is_pdf:
            chunks = await extract_pdf_text(content)
        elif is_docx:
            chunks = await extract_docx_text(content)
        else:
            raise ValueError(f"Unsupported file type: {fp}")

    tu.logger.info(f"Extracted {len(chunks)} chunks")
    if not chunks:
        raise ValueError(f"No chunks found for file: {fp}")

    # get the embeddings
    model = get_llm("gpt-4o")
    chunk_texts = list(tu.batched([c.content for c in chunks], 15))
    embeddings = []
    for chunk_text in chunk_texts:
        embeddings.extend((await model.embedding_async(chunk_text)).embedding)
    tu.logger.info(
        f"Generated embeddings: {len(embeddings)} chunks x {len(embeddings[0])} dimensions"
    )

    # upload to supabase
    tu.logger.info(f"Uploading to supabase: {filename}")
    client = get_supabase_client()
    resp = client.storage.from_("source-files").upload(
        path=filename,
        file=content,
        file_options={
            "cache-control": "3600",
            "upsert": "true",
        },
    )
    tu.logger.info(f"Uploaded to supabase: {resp.path}")
    tu.logger.info(f"File size: {file_size} bytes")

    # Save to database
    tu.logger.info(f"Saving to database: {filename}")
    session = get_db_session(sync=False)
    try:
        # Create source document
        source_doc = SourceDocument(
            filename=resp.path,
            file_size_bytes=file_size,
            status=DocumentStatus.PROCESSING,
            active=True,
        )
        session.add(source_doc)
        await session.flush()  # To get the ID
        await session.refresh(source_doc)

        # Create chunks
        chunk_records = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_record = DocumentChunk(
                source_document_id=source_doc.id,
                content=chunk.content,
                embedding=embedding,
                location=chunk.loc,
                model_used=model.model_id,
            )
            chunk_records.append(chunk_record)
            session.add(chunk_record)

        # Update source document status to completed
        source_doc.status = DocumentStatus.COMPLETED

        await session.commit()
        tu.logger.info(
            f"Successfully saved document '{filename}' with {len(chunk_records)} chunks to database"
        )
        tu.logger.info(f"Source document ID: {source_doc.id}")

    except Exception as e:
        await session.rollback()
        tu.logger.info(f"Error saving to database: {e}")
        raise
    finally:
        await session.close()
    tu.logger.info(
        f"Successfully loaded document '{filename}' with {len(chunk_records)} chunks to database"
    )


async def main(fp: str):
    await asyncio.gather(_main(fp))


if __name__ == "__main__":
    Fire(main)
