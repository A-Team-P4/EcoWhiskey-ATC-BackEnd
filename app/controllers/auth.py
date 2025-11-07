"""Authentication controller providing login endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.config.settings import settings
from app.controllers.dependencies import SessionDep
from app.models.user import User as UserModel
from app.telemetry import increment_login
from app.services import EmailServiceError, send_email
from app.utils import (
    create_access_token,
    generate_temporary_password,
    hash_password,
    verify_password,
)
from app.views import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    SchoolResponse,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: SessionDep,
) -> TokenResponse:
    """Validate credentials and issue a JWT access token."""

    result = await session.execute(
        select(UserModel).where(UserModel.email == payload.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(subject=str(user.id), user=user)
    expires_in = settings.security.access_token_expires_minutes * 60
    full_name = f"{user.first_name} {user.last_name}".strip()

    increment_login()

    school = SchoolResponse.model_validate(user.school) if user.school else None
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        account_type=user.account_type.value,
        name=full_name,
        school=school,
    )


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: SessionDep,
) -> ForgotPasswordResponse:
    """Generate a temporary password and email it to the requester."""

    result = await session.execute(
        select(UserModel).where(UserModel.email == payload.email)
    )
    user = result.scalar_one_or_none()

    if user is None:
        return ForgotPasswordResponse(
            exists=False,
            message="No existe una cuenta asociada a ese correo.",
        )

    temporary_password = generate_temporary_password()
    user.password_hash = hash_password(temporary_password)

    subject = "Recuperación de contraseña"
    body = (
        f"Hola {user.first_name},\n\n"
        "Recibimos una solicitud para restablecer tu contraseña de EcoWhiskey ATC.\n"
        f"Tu contraseña temporal es: {temporary_password}\n\n"
        "Inicia sesión con esta contraseña y cámbiala inmediatamente por una nueva.\n\n"
        "Equipo EcoWhiskey ATC"
    )

    try:
        await send_email(recipient=user.email, subject=subject, body=body)
    except EmailServiceError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail="No fue posible enviar el correo de recuperación. Inténtalo más tarde.",
        ) from exc

    await session.commit()
    return ForgotPasswordResponse(
        exists=True,
        message="Se envió una contraseña temporal al correo registrado.",
    )
