import jwt
import time
from collections import defaultdict, deque

from tuneapi import tu
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from src.settings import settings
from src.wire import SuccessResponse, Error
from src.db import UserProfile, UserRole

# Constants
JWT_SECRET = settings.jwt_secret
JWT_ALGORITHM = settings.jwt_algorithm
rate_limit_store = defaultdict(lambda: deque())


async def rate_limiting_middleware(request: Request, call_next):
    # Get client IP
    client_ip = request.client.host

    # Rate limits
    user_limit = 100  # requests per minute for regular users
    admin_limit = 1000  # requests per minute for admin users
    window = 60  # 1 minute window

    current_time = time.time()

    # Clean old entries
    user_requests = rate_limit_store[client_ip]
    while user_requests and user_requests[0] < current_time - window:
        user_requests.popleft()

    # Check if admin endpoint (higher limits)
    is_admin_endpoint = request.url.path.startswith("/api/admin")
    limit = admin_limit if is_admin_endpoint else user_limit

    # Check rate limit
    if len(user_requests) >= limit:
        return JSONResponse(
            content=Error(
                code="RATE_LIMIT_EXCEEDED",
                message=f"Rate limit exceeded. Maximum {limit} requests per minute.",
                details={"retry_after": 60},
            ).model_dump(),
            status_code=429,
        )

    # Add current request
    user_requests.append(current_time)

    response = await call_next(request)
    return response


async def jwt_auth_middleware(request: Request, call_next):
    # Skip auth for public endpoints
    public_paths = [
        "/api/auth/login",
        "/api/auth/register",
        "/docs",
        "/openapi.json",
    ]

    if any(request.url.path.startswith(path) for path in public_paths):
        return await call_next(request)
    
        # Skip auth for all non-API routes (frontend routes, static files, etc.)
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    
    is_refresh_endpoint = request.url.path.startswith("/api/auth/refresh")


    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(
            content=Error(
                code="UNAUTHORIZED",
                message="Missing or invalid authorization header",
            ).model_dump(),
            status_code=401,
        )

    token = auth_header.split(" ")[1]
    session = None
    try:
        if is_refresh_endpoint:
            # This is the refresh token flow, we don't need to check if the token is expired
            payload = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=[JWT_ALGORITHM],
                options={"verify_exp": False},
            )
        else:
            # This is the normal flow, we need to check if the token is expired
            payload = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=[JWT_ALGORITHM],
            )
            if payload.get("exp") < tu.SimplerTimes.get_now_datetime().timestamp():
                return JSONResponse(
                    content=Error(
                        code="TOKEN_EXPIRED",
                        message="Token has expired",
                    ).model_dump(),
                    status_code=401,
                )

        # Add user info to request state and check if signed in
        session = request.app.state.db_session_factory()
        user_id = payload.get("user_id")
        if user_id:
            query = select(UserProfile).where(UserProfile.id == user_id)
            result = await session.execute(query)
            user: UserProfile | None = result.scalar_one_or_none()
            if user:
                # Check if user is signed in
                if not user.is_signed_in:
                    return JSONResponse(
                        content=Error(
                            code="USER_NOT_FOUND",
                            message="User not found",
                        ).model_dump(),
                        status_code=404,
                    )
                request.state.user = user
            else:
                return JSONResponse(
                    content=Error(
                        code="USER_NOT_FOUND",
                        message="User not found",
                    ).model_dump(),
                    status_code=404,
                )

    except jwt.InvalidTokenError:
        return JSONResponse(
            content=Error(
                code="INVALID_TOKEN",
                message="Invalid authentication token",
            ).model_dump(),
            status_code=401,
        )
    finally:
        if session:
            await session.close()

    response = await call_next(request)
    return response


async def admin_auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/admin"):
        # Check if user role is admin (set by jwt_auth_middleware)
        user: UserProfile | None = getattr(request.state, "user", None)
        if not user or user.role != UserRole.ADMIN:
            # Return 404 instead of 403 to hide admin endpoints
            return JSONResponse(
                content=Error(code="NOT_FOUND", message="Not Found").model_dump(),
                status_code=404,
            )

    response = await call_next(request)
    return response


def setup_middlewares(app: FastAPI):
    # Apply middlewares in correct order (last added = first executed)
    app.middleware("http")(admin_auth_middleware)
    app.middleware("http")(jwt_auth_middleware)
    app.middleware("http")(rate_limiting_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app
