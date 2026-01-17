#!/usr/bin/env python3
"""Reset a user's password in the database."""

import sys
from sqlmodel import Session, select, create_engine

from api.models import User
from api.routes.auth import get_password_hash

# Database connection
DATABASE_URL = "postgresql://overlay:overlay_dev_password@localhost:5432/overlay_dev"

def reset_password(email: str, new_password: str):
    """Reset password for a user."""
    engine = create_engine(DATABASE_URL)
    
    with Session(engine) as session:
        # Find user
        statement = select(User).where(User.email == email, User.deleted_at.is_(None))
        user = session.exec(statement).first()
        
        if not user:
            print(f"Error: User with email '{email}' not found")
            return False
        
        # Update password
        user.password_hash = get_password_hash(new_password)
        session.add(user)
        session.commit()
        
        print(f"✅ Password reset successfully for {email}")
        return True

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python reset_user_password.py <email> <new_password>")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    reset_password(email, password)
