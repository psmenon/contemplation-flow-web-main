from tuneapi import tu

import os
import asyncio
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import async_sessionmaker

from src import db, middlewares
from src.db import dispose_background_engine
from src.services import (
    admin as admin_svc,
    audio as audio_svc,
    auth as auth_svc,
    chat as chat_svc,
    content as content_svc,
)
from src.dependencies import check_ffmpeg, get_api_token
from src.content.parallel_video import pre_generate_common_images


async def _setup_db(app: FastAPI):
    tu.logger.info("Setting up the database")
    db_engine = db.connect_to_postgres(sync=False)
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    app.state.db_engine = db_engine
    app.state.db_session_factory = session_factory

async def _setup_optimizations(app: FastAPI):
    """Setup performance optimizations"""
    tu.logger.info("Setting up performance optimizations...")
    
    # Pre-generate common meditation images for faster video generation
    try:
        await pre_generate_common_images()
        tu.logger.info("Performance optimizations setup complete")
    except Exception as e:
        tu.logger.error(f"Failed to setup optimizations: {e}")
        # Don't fail startup if optimizations fail

async def _close_db(app: FastAPI):
    tu.logger.info("Closing the database")
    db_engine = app.state.db_engine
    await db_engine.dispose()
    
    # Also dispose the background engine
    await dispose_background_engine()


# The app itself


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup
    await _setup_db(app)
    # Don't pre-generate images at startup - too slow!
    # await _setup_optimizations(app)
    
    # Start background pre-generation after server is up
    asyncio.create_task(background_image_pregeneration())
    
    yield

    # Cleanup
    await _close_db(app)

async def background_image_pregeneration():
    """Pre-generate images in background after server startup"""
    # Wait a bit for server to fully start
    await asyncio.sleep(30)  # Wait 30 seconds after startup
    
    try:
        tu.logger.info("Starting background image pre-generation...")
        await pre_generate_common_images()
    except Exception as e:
        tu.logger.error(f"Background image pre-generation failed: {e}")
        # Don't crash the server if this fails


def get_app() -> FastAPI:
    # Run before using
    check_ffmpeg()

    # FastAPI
    app = FastAPI(lifespan=lifespan)
    app = middlewares.setup_middlewares(app)
    auth_dependency = [Depends(get_api_token)]

    # fmt: off
    # add paths
    app.add_api_route("/api/auth/register", auth_svc.new_user, methods=["POST"], tags=["auth"])
    app.add_api_route("/api/auth/login", auth_svc.login, methods=["POST"], tags=["auth"])
    app.add_api_route("/api/auth/me", auth_svc.get_current_user, methods=["GET"], tags=["auth"], dependencies=auth_dependency)
    app.add_api_route("/api/auth/refresh", auth_svc.refresh_jwt, methods=["POST"], tags=["auth"], dependencies=auth_dependency)
    app.add_api_route("/api/auth/logout", auth_svc.logout, methods=["POST"], tags=["auth"], dependencies=auth_dependency)

    # chat
    app.add_api_route("/api/chat", chat_svc.get_conversations, methods=["GET"], tags=["chat"], dependencies=auth_dependency)
    app.add_api_route("/api/chat", chat_svc.create_conversation, methods=["POST"], tags=["chat"], dependencies=auth_dependency)
    app.add_api_route("/api/chat/{conversation_id}", chat_svc.get_conversation, methods=["GET"], tags=["chat"], dependencies=auth_dependency)
    app.add_api_route("/api/chat/{conversation_id}", chat_svc.chat_completions, methods=["POST"], tags=["chat"], dependencies=auth_dependency)
    app.add_api_route("/api/chat/{conversation_id}", chat_svc.delete_conversation, methods=["DELETE"], tags=["chat"], dependencies=auth_dependency)
    app.add_api_route("/api/chat/{conversation_id}/title", chat_svc.update_conversation_title, methods=["PUT"], tags=["chat"], dependencies=auth_dependency)
    app.add_api_route("/api/chat/{conversation_id}/feedback", chat_svc.submit_conversation_feedback, methods=["POST"], tags=["chat"], dependencies=auth_dependency)

    # content
    app.add_api_route("/api/content", content_svc.create_content, methods=["POST"], tags=["content"], dependencies=auth_dependency)
    app.add_api_route("/api/content/{content_id}", content_svc.get_content, methods=["GET"], tags=["content"], dependencies=auth_dependency)

    # # audio
    # app.add_api_route("/api/speech/transcribe", audio_svc.transcribe_audio, methods=["POST"], tags=["audio"], dependencies=auth_dependency)
    # app.add_api_route("/api/tts/generate", audio_svc.generate_speech, methods=["POST"], tags=["audio"], dependencies=auth_dependency)

    # admin
    app.add_api_route("/api/admin/users", admin_svc.list_users, methods=["GET"], tags=["admin"], dependencies=auth_dependency)
    app.add_api_route("/api/admin/users/{user_id}", admin_svc.delete_user, methods=["DELETE"], tags=["admin"], dependencies=auth_dependency)
    app.add_api_route("/api/admin/content/{content_id}", admin_svc.delete_content, methods=["DELETE"], tags=["admin"], dependencies=auth_dependency)
    app.add_api_route("/api/admin/feedback", admin_svc.get_feedback, methods=["GET"], tags=["admin"], dependencies=auth_dependency)
    app.add_api_route("/api/admin/source-data/list", admin_svc.list_source_data, methods=["GET"], tags=["admin"], dependencies=auth_dependency)
    # fmt: on

    # Health check endpoint for Render.com
    @app.get("/health")
    async def health_check():
        """Health check endpoint for Render.com monitoring"""
        return {"status": "healthy", "timestamp": tu.SimplerTimes.get_now_datetime().isoformat()}

    # Catch-all route for SPA (Single Page Application) - must be last
    ui_path = tu.joinp(tu.folder(__file__), "ui")
    app.mount("/static", StaticFiles(directory=ui_path), name="static")

    @app.get("/{full_path:path}")
    async def catch_all(full_path: str):
        """Serve the React app for all non-API routes"""
        # Don't serve index.html for API routes
        if full_path.startswith("api/"):
            return {"error": "Not found"}, 404

        # Serve index.html for all other routes (SPA routing)
        index_file = os.path.join(ui_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        else:
            return {"error": "Frontend not found"}, 404

    return app


def start_server():
    # create a new asyncio event loop and then run the app
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(get_app().run())
