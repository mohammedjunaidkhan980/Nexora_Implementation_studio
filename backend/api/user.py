from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
from model.organization import Organization, OrganizationMember
from model.user import User
from schema.user import (
    UserRegister,
    UserLogin,
    UserResponse,
    TokenResponse,
    UserOrganizationResponse,
)
from security import get_current_user, hash_password, verify_password, generate_jwt

router = APIRouter(prefix="/user", tags=["User"])


def _create_access_token(email: str, password: str, db: Session) -> TokenResponse:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    token = generate_jwt(user_id=user.id, email=user.email)
    return TokenResponse(access_token=token)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    return _create_access_token(payload.email, payload.password, db)


@router.post("/token", response_model=TokenResponse)
def token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _create_access_token(form_data.username, form_data.password, db)


@router.get("/organizations", response_model=list[UserOrganizationResponse])
def list_user_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    memberships = (
        db.query(OrganizationMember, Organization.name)
        .join(Organization, Organization.id == OrganizationMember.organization_id)
        .filter(OrganizationMember.user_id == current_user.id)
        .order_by(OrganizationMember.id)
        .all()
    )
    return [
        UserOrganizationResponse(
            organization_id=membership.organization_id,
            organization_name=organization_name,
            role=membership.role,
        )
        for membership, organization_name in memberships
    ]
