from tuneapi import tu

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt
import datetime
from uuid import uuid4

# from src.wire import (
#     LoginRequest,
#     LogoutRequest,
#     AuthResponse,
#     User,
#     RefreshTokenRequest,
#     NewUserRequest,
# )

from src import wire as w
from src.db import (
    get_db_session_fa,
    UserProfile,
    OTPSession,
    OTPSessionType,
    OTPStatus,
    UserRole,
)
from src.dependencies import get_current_user
from src.settings import settings


def create_jwt_tokens(user_id: str) -> tuple[str, str]:
    """Create access and refresh tokens for a user"""
    now = tu.SimplerTimes.get_now_datetime()

    # Access token - expires in 1 hour
    access_payload = {
        "user_id": str(user_id),
        "exp": now + datetime.timedelta(hours=1),
        "iat": now,
        "type": "access",
    }
    access_token = jwt.encode(
        access_payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    # Refresh token - expires in 30 days
    refresh_payload = {
        "user_id": str(user_id),
        "exp": now + datetime.timedelta(days=30),
        "iat": now,
        "type": "refresh",
    }
    refresh_token = jwt.encode(
        refresh_payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    return access_token, refresh_token


# Authentication
async def login(
    request: w.LoginRequest,
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.AuthResponse | w.SuccessResponse:
    """POST /api/auth/login - User login (two-step: send OTP, then verify)"""

    # Step 1: If no OTP provided, initiate login process
    if not request.otp:
        # Check if user exists
        user_query = select(UserProfile).where(
            UserProfile.phone_number == request.phone_number
        )
        result = await session.execute(user_query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Create OTP session for login
        otp_session = OTPSession(
            phone_number=request.phone_number,
            otpless_request_id=str(
                uuid4()
            ),  # In a real implementation, this would come from OTP service
            session_type=OTPSessionType.LOGIN,
            status=OTPStatus.PENDING,
            expires_at=tu.SimplerTimes.get_now_datetime()
            + datetime.timedelta(minutes=10),
        )

        session.add(otp_session)
        await session.commit()

        # In a real implementation, you would send OTP via SMS here
        # For now, we'll return a mock response
        return w.SuccessResponse(
            success=True,
            message=f"OTP sent to your phone number {request.phone_number}",
            data={
                "phone_number": request.phone_number,
                "expires_in": 600,  # 10 minutes
            },
        )

    # Step 2: Verify OTP and complete login
    else:
        # Find the OTP session
        otp_query = (
            select(OTPSession)
            .where(
                OTPSession.phone_number == request.phone_number,
                OTPSession.session_type == OTPSessionType.LOGIN,
                OTPSession.status == OTPStatus.PENDING,
                OTPSession.expires_at > tu.SimplerTimes.get_now_datetime(),
            )
            .order_by(OTPSession.created_at.desc())
        )

        result = await session.execute(otp_query)
        otp_session = result.scalar_one_or_none()
        if not otp_session:
            raise HTTPException(
                status_code=400, detail="Invalid or expired OTP session"
            )

        # Check if max attempts exceeded
        if otp_session.attempts >= otp_session.max_attempts:
            otp_session.status = OTPStatus.FAILED
            await session.commit()
            raise HTTPException(status_code=400, detail="Maximum OTP attempts exceeded")

        # Increment attempts
        otp_session.attempts += 1

        # In a real implementation, you would verify the OTP with the service
        # For now, we'll accept any OTP (you should replace this with actual verification)
        if request.otp != "123456":  # Mock OTP - replace with actual verification
            await session.commit()
            raise HTTPException(status_code=400, detail="Invalid OTP")

        # Mark OTP as verified
        otp_session.status = OTPStatus.VERIFIED
        otp_session.verified_at = tu.SimplerTimes.get_now_datetime()

        # Get user and update last active
        user_query = select(UserProfile).where(
            UserProfile.phone_number == request.phone_number
        )
        result = await session.execute(user_query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update last active timestamp and set signed in
        user.last_active_at = tu.SimplerTimes.get_now_datetime()
        user.is_signed_in = True
        await session.commit()
        await session.refresh(user)

        # Generate JWT tokens
        user = await user.to_bm()
        access_token, refresh_token = create_jwt_tokens(user.id)

        # Return auth response
        return w.AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user,
        )


async def logout(
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.SuccessResponse:
    """POST /api/auth/logout - User logout and session termination"""

    # Fetch the user in the current session to ensure changes are tracked
    user_query = select(UserProfile).where(UserProfile.id == current_user.id)
    result = await session.execute(user_query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Set the user as signed out
    user.is_signed_in = False
    user.last_active_at = tu.SimplerTimes.get_now_datetime()
    await session.commit()

    # Log the logout event
    tu.logger.info(f"User {user.id} logged out successfully")

    return w.SuccessResponse(
        success=True,
        message="Successfully logged out",
    )


async def new_user(
    request: w.NewUserRequest,
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.SuccessResponse:
    """POST /api/auth/register - New user registration"""
    if not request.name:
        raise HTTPException(
            status_code=400,
            detail="Name is required for registration of a new user",
        )
    if not request.phone_number:
        raise HTTPException(
            status_code=400,
            detail="Phone number is required for registration of a new user",
        )

    # Check if user already exists
    existing_user_query = select(UserProfile).where(
        UserProfile.phone_number == request.phone_number
    )
    result = await session.execute(existing_user_query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=400, detail="User with this phone number already exists"
        )

    # Create mock OTP session for registration
    # In a real implementation, this would interact with an OTP service
    mock_otp_code = "123456"  # Mock OTP code for testing
    otp_session = OTPSession(
        phone_number=request.phone_number,
        otpless_request_id=str(uuid4()),
        session_type=OTPSessionType.REGISTER,
        status=OTPStatus.PENDING,
        expires_at=tu.SimplerTimes.get_now_datetime() + datetime.timedelta(minutes=10),
    )

    # For development purposes only - log the OTP code
    print(f"MOCK OTP for {request.phone_number}: {mock_otp_code}")

    session.add(otp_session)
    await session.commit()

    # Create new user
    new_user = UserProfile(
        phone_number=request.phone_number,
        name=request.name,
        phone_verified=True,  # Since this is registration, we mark as verified
        role=UserRole.USER,
    )

    session.add(new_user)
    await session.commit()

    # Return success response
    return w.SuccessResponse(
        success=True,
        message=f"User {request.phone_number} registered successfully",
    )


async def get_current_user(
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.User:
    """GET /api/auth/me - Get current user profile"""
    # Update last active timestamp
    current_user.last_active_at = tu.SimplerTimes.get_now_datetime()
    await session.commit()

    # Return user profile
    return await current_user.to_bm()


async def refresh_jwt(
    request: w.RefreshTokenRequest,
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.AuthResponse:
    """POST /api/auth/refresh - Refresh authentication tokens"""

    try:
        # Decode and verify refresh token
        payload = jwt.decode(
            request.refresh_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Check if it's a refresh token
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Invalid token type")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token payload")

    # Get user
    user_query = select(UserProfile).where(UserProfile.id == user_id)
    result = await session.execute(user_query)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user is signed in
    if not user.is_signed_in:
        raise HTTPException(status_code=401, detail="User has been logged out")

    # Update last active timestamp
    user.last_active_at = tu.SimplerTimes.get_now_datetime()
    await session.commit()
    await session.refresh(user)

    # Generate new tokens
    access_token, refresh_token = create_jwt_tokens(user.id)

    # Return new auth response
    return w.AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=await user.to_bm(),
    )
