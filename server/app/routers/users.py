from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..schemas.user import User, UserCreate, UserBase, UserRole
from ..models_db.user import User as UserDB
from ..database import get_db
from ..core.oauth2 import get_current_user, get_current_admin_user

router = APIRouter(prefix="/users", tags=["users"])

def get_user_by_email(db: Session, email: str):
    """Get user by email from database"""
    return db.query(UserDB).filter(UserDB.email == email).first()

def get_user_by_id(db: Session, user_id: int):
    """Get user by ID from database"""
    return db.query(UserDB).filter(UserDB.id == user_id).first()

@router.get("/", response_model=List[User])
async def get_users(db: Session = Depends(get_db), current_admin: UserDB = Depends(get_current_admin_user)):
    """Get all users (admin only)"""
    users = db.query(UserDB).all()
    return [User(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role
    ) for user in users]

@router.get("/me", response_model=User)
async def get_current_user_profile(current_user: UserDB = Depends(get_current_user)):
    """Get current user's profile"""
    return User(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role
    )

@router.get("/{user_id}", response_model=User)
async def get_user(user_id: int, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Get user by ID"""
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return User(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role
    )

@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: int, 
    user_update: UserBase,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user)
):
    """Update user by ID - Users can only update their own profile, admins can update any profile"""
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if current user can update this user (own profile or admin)
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile"
        )
    
    # Check if email is being changed and if new email already exists
    if user_update.email != user.email:
        existing_user = get_user_by_email(db, user_update.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
    
    # Update user data
    try:
        user.email = user_update.email
        user.name = user_update.name
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update user"
        )
    
    return User(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role
    )

@router.delete("/{user_id}")
async def delete_user(
    user_id: int, 
    db: Session = Depends(get_db), 
    current_user: UserDB = Depends(get_current_user)
):
    """Delete user by ID - Only admins can delete users, and users cannot delete themselves"""
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only admins can delete users
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete users"
        )
    
    # Prevent admins from deleting their own account
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Hard delete the user from database
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}
