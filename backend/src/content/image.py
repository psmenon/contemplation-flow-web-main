import uuid
from io import BytesIO
from tuneapi import tu
import random
from textwrap import dedent

from supabase import Client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from PIL import Image, ImageDraw, ImageFont
import textwrap

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


CONTEMPLATION_PROMPTS = [
    "Soft morning light filtering through bamboo leaves",
    "A single white lotus floating on still water",
    "Gentle waves lapping at a pebble beach at dawn",
    "Misty mountains reflected in a calm lake",
    "A sleeping cat curled up in a sunny window",
    "Dewdrops on grass blades in early morning",
    "A wooden dock extending into a serene pond",
    "Soft candlelight flickering in a quiet room",
    "Cherry blossoms drifting down like snow",
    "A peaceful garden path lined with lavender",
    "Moonlight streaming through white curtains",
    "A single bird perched on a bare branch",
    "Smooth river stones stacked in meditation",
    "Soft clouds drifting across a pastel sky",
    "A cozy reading nook with warm blankets",
    "Sunbeams piercing through forest canopy",
    "A field of tall grass swaying in gentle breeze",
    "Ripples spreading across a mountain lake",
    "A butterfly resting on a wildflower",
    "Soft fog rolling over rolling hills",
    "A peaceful zen garden with raked sand",
    "Warm golden hour light in an empty meadow",
    "A single feather floating on calm water",
    "Gentle rain drops on a peaceful pond",
    "A hammock swaying between two old trees",
    "Soft pastel sunset colors over wheat fields",
    "A quiet forest clearing with dappled sunlight",
    "Calm ocean waves under a star-filled sky",
    "A single candle flame in complete darkness",
    "Morning mist rising from a tranquil valley",
    "Peaceful zen garden with flowing water and soft sunlight",
    "Serene mountain lake at sunset with gentle ripples",
    "Tranquil forest clearing with dappled morning light",
    "Misty mountains with flowing clouds at dawn",
    "Peaceful bamboo grove with soft filtered light",
    "Quiet temple garden with stone lanterns and cherry blossoms",
    "Serene pond with lotus flowers and reflections",
    "Calm desert dunes under a twilight sky",
    "Peaceful meadow with wildflowers and gentle breeze",
]


# ------------------------------------------------------------
# Background task and main functions
# ------------------------------------------------------------


async def generate_image_content(
    content_id: str,
    conversation_id: str,
    message_id: str,
) -> None:
    """Background task to generate image content and update the database record"""

    spb_client = get_supabase_client()

    async with get_background_session() as session:
        try:
            tu.logger.info(f"Starting background image generation for content {content_id}")

            # Generate the image content
            content_path, cc_text = await generate_contemplation_card_sync(
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
                content_generation.cc_text = cc_text
                await session.commit()
                tu.logger.info(
                    f"Successfully completed image generation for content {content_id}"
                )
            else:
                tu.logger.error(f"ContentGeneration record not found for id {content_id}")
                # No changes were made, but ensure session is clean
                await session.rollback()

        except Exception as e:
            tu.logger.error(
                f"Error in background image generation for content {content_id}: {e}"
            )
            # Session will be automatically rolled back by the context manager
            raise


async def generate_contemplation_card_sync(
    session: AsyncSession,
    conversation_id: str,
    message_id: str,
    spb_client: Client,
    content_id: str,
) -> tuple[str, str]:
    """Generate contemplation card synchronously and return content_path and cc_text"""

    prompt = random.choice(CONTEMPLATION_PROMPTS)
    quote = await _get_quote_from_citations_or_random(
        session, conversation_id, message_id
    )

    # Get the conversation to get the user_id
    query = select(Conversation).where(Conversation.id == conversation_id)
    result = await session.execute(query)
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise ValueError(f"Conversation with id {conversation_id} not found")

    # image gen
    tu.logger.info(
        f"Generating contemplation card for conversation {conversation_id}/{message_id}"
    )
    pil_image = await _generate_image(prompt)

    # add caption to the image
    with_caption = add_caption_to_image(pil_image, quote)
    tu.logger.info(f"Added caption to image: {with_caption.size}")

    # create content path
    content_path = f"contemplation-cards/{content_id}.png"

    # Convert PIL image to bytes for upload
    img_buffer = BytesIO()
    with_caption.save(img_buffer, format="PNG")
    img_bytes = img_buffer.getvalue()

    # upload to the supabase storage
    tu.logger.info(f"Uploading image to supabase: {content_path}")
    spb_client.storage.from_("generations").upload(
        content_path,
        img_bytes,
        {"content-type": "image/png"},
    )

    tu.logger.info(f"Successfully created image content generation: {content_id}")
    return content_path, prompt


async def generate_contemplation_card(
    session: AsyncSession,
    conversation_id: str,
    message_id: str,
    spb_client: Client,
) -> ContentGeneration:
    """Legacy function - kept for backward compatibility"""

    # Generate content ID
    content_id = str(uuid.uuid4())

    # Call the sync version
    content_path, cc_text = await generate_contemplation_card_sync(
        session=session,
        conversation_id=conversation_id,
        message_id=message_id,
        spb_client=spb_client,
        content_id=content_id,
    )

    # Get the conversation to get the user_id
    query = select(Conversation).where(Conversation.id == conversation_id)
    result = await session.execute(query)
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise ValueError(f"Conversation with id {conversation_id} not found")

    # Create ContentGeneration record
    content_generation = ContentGeneration(
        id=content_id,
        user_id=conversation.user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        content_type=ContentType.IMAGE,
        content_path=content_path,
        cc_text=cc_text,
        cc_theme="nature_sunset",
    )

    session.add(content_generation)
    await session.commit()
    await session.refresh(content_generation)

    return content_generation


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------


async def _get_quote_from_citations_or_random(
    session: AsyncSession,
    conversation_id: str,
    message_id: str,
) -> str:
    """
    Check for citations in the current message or conversation.
    If none exist, pick a random source file and generate a quote from random chunks.
    """
    model = get_llm("gpt-4o")

    # First, get the current message
    current_message_query = select(Message).where(Message.id == message_id)
    current_message_result = await session.execute(current_message_query)
    current_message = current_message_result.scalar_one_or_none()

    # Check if current message has citations
    if current_message and current_message.citations:
        tu.logger.info(
            f"Found citations in current message: {len(current_message.citations)}"
        )
        # Get chunks from cited documents
        cited_filenames = [citation.name for citation in current_message.citations]
        chunks_query = (
            select(DocumentChunk.content, SourceDocument.filename)
            .join(SourceDocument)
            .where(
                SourceDocument.filename.in_(cited_filenames),
                SourceDocument.active == True,
            )
            .limit(5)  # Get a few chunks from cited documents
        )
        chunks_result = await session.execute(chunks_query)
        cited_chunks = chunks_result.all()

        if cited_chunks:
            chunk_texts = [
                f"From {filename}: {content}" for content, filename in cited_chunks
            ]
            source_text = "\n\n".join(chunk_texts[:3])  # Use first 3 chunks
        else:
            # Fallback to random if cited documents have no chunks
            source_text = await _get_random_chunks_text(session)
    else:
        # Check if any message in the conversation has citations
        conversation_messages_query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .options(selectinload(Message.citations))
        )
        conversation_messages_result = await session.execute(
            conversation_messages_query
        )
        conversation_messages = conversation_messages_result.scalars().all()

        # Look for any message with citations
        all_citations = []
        for msg in conversation_messages:
            if msg.citations:
                all_citations.extend(msg.citations)

        if all_citations:
            tu.logger.info(f"Found citations in conversation: {len(all_citations)}")
            # Get chunks from any cited documents in the conversation
            cited_filenames = [citation.name for citation in all_citations]
            chunks_query = (
                select(DocumentChunk.content, SourceDocument.filename)
                .join(SourceDocument)
                .where(
                    SourceDocument.filename.in_(cited_filenames),
                    SourceDocument.active == True,
                )
                .limit(5)
            )
            chunks_result = await session.execute(chunks_query)
            cited_chunks = chunks_result.all()

            if cited_chunks:
                chunk_texts = [
                    f"From {filename}: {content}" for content, filename in cited_chunks
                ]
                source_text = "\n\n".join(chunk_texts[:3])
            else:
                source_text = await _get_random_chunks_text(session)
        else:
            tu.logger.info("No citations found, using random source file")
            source_text = await _get_random_chunks_text(session)

    # Generate a quote using LLM
    quote_prompt = dedent(
        f"""
    Based on the following spiritual/contemplative text, create a short, meaningful quote (1-2 sentences max) that captures the essence of the wisdom or insight. The quote should be inspiring, peaceful, and suitable for contemplation.

    Source text:
    {source_text}

    Generate only the quote, without quotation marks or attribution.
    """
    )

    quote_response = await model.chat_async(quote_prompt)
    return quote_response.strip()


async def _get_random_chunks_text(session: AsyncSession) -> str:
    """Get random chunks from a random source document."""

    # Get a random active source document
    random_doc_query = (
        select(SourceDocument)
        .where(SourceDocument.active == True)
        .order_by(func.random())
        .limit(1)
    )
    random_doc_result = await session.execute(random_doc_query)
    random_doc = random_doc_result.scalar_one_or_none()

    if not random_doc:
        tu.logger.warning("No active source documents found")
        return "The journey of a thousand miles begins with a single step."

    # Get random chunks from this document
    chunks_query = (
        select(DocumentChunk.content)
        .where(DocumentChunk.source_document_id == random_doc.id)
        .order_by(func.random())
        .limit(3)  # Get 3 random chunks
    )
    chunks_result = await session.execute(chunks_query)
    chunks = chunks_result.scalars().all()

    if not chunks:
        tu.logger.warning(f"No chunks found for document {random_doc.filename}")
        return "In silence, we find the deepest truths."

    return "\n\n".join(chunks)


async def _generate_image(prompt: str) -> Image.Image:
    tu.logger.info(f"Generating image for prompt: {prompt}")
    model = get_llm("gpt-4o")
    img_gen_response = await model.image_gen_async(
        prompt=prompt,
        n=1,
        size="1792x1024",
        quality="standard",
    )
    tu.logger.info(f"Generated image: {img_gen_response.image.size}")
    pil_image = img_gen_response.image
    return pil_image


def add_caption_to_image(
    image: Image.Image,
    caption_text: str,
    font_size=40,
    padding=20,
    max_width_ratio=0.9,
):
    """
    Add a caption below a PIL image with white background.

    Args:
        image: PIL Image object
        caption_text: String for the caption (can be multi-line)
        font_size: Font size for the caption
        padding: Padding around the caption text
        max_width_ratio: Maximum width ratio for text wrapping (0.9 = 90% of image width)

    Returns:
        PIL Image with caption added below
    """

    # Get original image dimensions
    orig_width, orig_height = image.size

    # Try to load a font, fall back to default if not available
    font_fp = tu.joinp(
        tu.joinp(tu.folder(__file__), "DM_Serif_Text"),
        "DMSerifText-Regular.ttf",
    )
    tu.logger.info(f"Loading font from {font_fp}")
    font = ImageFont.truetype(font_fp, font_size)

    # Create a temporary draw object to measure text
    temp_img = Image.new("RGB", (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)

    # Calculate maximum text width (90% of image width)
    max_text_width = int(orig_width * max_width_ratio)

    # Wrap text to fit within the image width
    wrapped_lines = []
    words = caption_text.split()
    current_line = ""

    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        bbox = temp_draw.textbbox((0, 0), test_line, font=font)
        text_width = bbox[2] - bbox[0]

        if text_width <= max_text_width:
            current_line = test_line
        else:
            if current_line:
                wrapped_lines.append(current_line)
                current_line = word
            else:
                # Single word is too long, add it anyway
                wrapped_lines.append(word)
                current_line = ""

    if current_line:
        wrapped_lines.append(current_line)

    # Limit to 2 lines as requested
    if len(wrapped_lines) > 2:
        wrapped_lines = wrapped_lines[:2]
        # Add ellipsis to the second line if text was truncated
        last_line = wrapped_lines[1]
        while True:
            test_line = last_line + "..."
            bbox = temp_draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]
            if text_width <= max_text_width:
                wrapped_lines[1] = test_line
                break
            # Remove last word and try again
            words_in_line = last_line.split()
            if len(words_in_line) <= 1:
                break
            last_line = " ".join(words_in_line[:-1])

    # Calculate text dimensions
    line_height = font_size + 4  # Add some line spacing
    total_text_height = len(wrapped_lines) * line_height

    # Calculate caption area height
    caption_height = total_text_height + (padding * 2)

    # Create new image with extended height
    new_height = orig_height + caption_height
    new_image = Image.new("RGB", (orig_width, new_height), "white")

    # Paste original image at the top
    new_image.paste(image, (0, 0))

    # Draw caption text
    draw = ImageDraw.Draw(new_image)

    # Calculate starting Y position for centered text
    text_start_y = orig_height + padding

    # Draw each line of text
    for i, line in enumerate(wrapped_lines):
        # Calculate text position (centered horizontally)
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (orig_width - text_width) // 2
        text_y = text_start_y + (i * line_height)

        # Draw the text
        draw.text((text_x, text_y), line, fill="black", font=font)

    return new_image
