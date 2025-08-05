from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Annotated
from jose import JWTError, jwt
from ..core.config import settings
from ..schemas.user import User, UserCreate, UserRole, PromoteUserRequest, RefreshTokenRequest
from ..models_db.user import User as UserDB
from ..database import get_db
from ..core.oauth2 import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_user,
    get_current_admin_user
)

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/refresh")
async def refresh_token(request: RefreshTokenRequest):
    """Exchange a valid refresh token for a new access token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(request.refresh_token, settings.secret_key, algorithms=["HS256"])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "refresh":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    # Optionally, check if user still exists and is active
    # Issue new access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": email}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

def get_user_by_email(db: Session, email: str):
    """Get user by email from database"""
    return db.query(UserDB).filter(UserDB.email == email).first()

def create_user_in_db(db: Session, user_data: UserCreate):
    """Create user in database"""
    hashed_password = get_password_hash(user_data.password)
    
    db_user = UserDB(
        email=user_data.email,
        name=user_data.name,
        hashed_password=hashed_password,
        role=user_data.role
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, email: str, password: str):
    """Authenticate user with email and password"""
    user = get_user_by_email(db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

@router.post("/register")
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user (always as regular user)"""
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    # Force role to USER regardless of input
    user_data.role = UserRole.USER
    user = create_user_in_db(db, user_data)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    refresh_token_expires = timedelta(days=7)
    refresh_token = create_access_token(
        data={"sub": user.email, "type": "refresh"}, expires_delta=refresh_token_expires
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value
        }
    }

# Endpoint for admin to promote a user to admin
@router.post("/promote-to-admin")
async def promote_to_admin(request: PromoteUserRequest, db: Session = Depends(get_db), current_admin: UserDB = Depends(get_current_admin_user)):
    """Promote a user to admin (admin only)"""
    user = get_user_by_email(db, request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    if user.role == UserRole.ADMIN:
        return {"message": "User is already an admin"}
    user.role = UserRole.ADMIN
    db.commit()
    db.refresh(user)
    return {
        "message": f"User {user.email} promoted to admin",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value
        }
    }

@router.post("/login")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    """Login user and return access and refresh tokens"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    refresh_token_expires = timedelta(days=7)
    refresh_token = create_access_token(
        data={"sub": user.email, "type": "refresh"}, expires_delta=refresh_token_expires
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value
        }
    }


@router.post("/logout")
async def logout():
    """Logout user"""
    # For JWT tokens, logout is typically handled client-side
    # You might want to implement token blacklisting here
    return {"message": "Successfully logged out"}

@router.post("/forgot-password")
async def forgot_password(email: str, db: Session = Depends(get_db)):
    """Request password reset"""
    user = get_user_by_email(db, email)
    if not user:
        # Don't reveal if email exists or not for security
        return {"message": "If the email exists, a password reset link has been sent"}
    
    # TODO: Implement password reset email logic
    return {"message": "If the email exists, a password reset link has been sent"}

@router.post("/create-admin")
async def create_admin_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Create the first admin user - only works if no admin exists"""
    # Check if any admin user already exists
    existing_admin = db.query(UserDB).filter(UserDB.role == UserRole.ADMIN).first()
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin user already exists"
        )
    
    # Check if user with this email already exists
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Force role to admin
    user_data.role = UserRole.ADMIN
    
    # Create admin user
    admin_user = create_user_in_db(db, user_data)
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": admin_user.email}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": admin_user.id,
            "email": admin_user.email,
            "name": admin_user.name,
            "role": admin_user.role.value
        },
        "message": "Admin user created successfully"
    }

@router.post("/reset-password")
async def reset_password(token: str, new_password: str):
    pass