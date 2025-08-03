from tuneapi import tu

from fastapi import File, UploadFile, Response, HTTPException
from fastapi import APIRouter
import tempfile
import os

from src.wire import TranscriptionResponse, TTSRequest
from src.settings import get_llm, settings

SUPPORTED_AUDIO_EXTENSIONS = ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"]


# Speech to Text
async def transcribe_audio(audio: UploadFile = File(...)) -> TranscriptionResponse:
    """POST /api/speech/transcribe - Convert audio to text"""
    extension = audio.filename.split(".")[-1].lower()
    if extension not in SUPPORTED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio file extension: {extension}. Supported formats are: {', '.join(SUPPORTED_AUDIO_EXTENSIONS)}",
        )

    contents = await audio.read()
    if len(contents) > settings.max_upload_file_size * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds the limit of {settings.max_upload_file_size}MB",
        )

    # Save uploaded file to a temporary file
    tu.logger.info(f"Saving audio to temporary file: {audio.filename}")
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as temp_file:
        temp_file.write(contents)
        temp_file_path = temp_file.name

    model = get_llm("gpt-4o")
    try:
        transcription = await model.speech_to_text_async(
            prompt="Transcribe this audio",
            audio=temp_file_path,
        )
        tu.logger.info(f"Transcription: {transcription.to('text')}")
        return TranscriptionResponse(text=transcription.to("text"))
    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_file_path)
        except Exception:
            pass  # Ignore cleanup errors


# Text to Speech
async def generate_speech(request: TTSRequest) -> Response:
    """POST /api/tts/generate - Generate speech from text (returns binary audio)"""
    if not request.text:
        raise HTTPException(status_code=400, detail="Text is required")
    model = get_llm("gpt-4o")
    audio = await model.text_to_speech_async(prompt=request.text, voice="shimmer")
    return Response(content=audio, media_type="audio/mpeg")
