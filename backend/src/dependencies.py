from tuneapi import tu

import subprocess
from fastapi import Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Annotated

from src.db import UserProfile

bearer_auth = HTTPBearer()


def get_current_user(request: Request) -> UserProfile:
    return request.state.user


def get_api_token(jwt: HTTPAuthorizationCredentials = Depends(bearer_auth)):
    """
    Dummy dependency to show the Authorization header in Swagger UI.
    The real authentication is handled by the middleware.
    """
    pass


def check_ffmpeg():
    """Check if FFmpeg is installed and accessible"""
    tu.logger.info("Checking if FFmpeg is installed")
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        tu.logger.info("FFmpeg is installed!")
        return True
    except FileNotFoundError:
        tu.logger.error("FFmpeg not found. Please install it first.")
        return False
