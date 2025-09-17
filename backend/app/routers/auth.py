from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.collection import Collection

from app import models, security
from app.database import get_user_collection

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post("/register", response_model=models.UserPublic, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: models.UserCreate,
    users: Collection = Depends(get_user_collection)
):
    """Register a new user in MongoDB."""
    if users.find_one({"email": user_in.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    hashed_password = security.get_password_hash(user_in.password)
    result = users.insert_one({"email": user_in.email, "hashed_password": hashed_password})

    return {"id": str(result.inserted_id), "email": user_in.email}


@router.post("/login", response_model=models.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    users: Collection = Depends(get_user_collection)
):
    """Login a user and return JWT access + refresh tokens."""
    user = users.find_one({"email": form_data.username})
    if not user or not security.verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = {"sub": user["email"]}
    access_token = security.create_access_token(data=token_data)
    refresh_token = security.create_refresh_token(data=token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
