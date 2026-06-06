"""SQLite database setup with SQLAlchemy ORM."""

from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./reviews.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ReviewRecord(Base):
    __tablename__ = "reviews"

    id = Column(String, primary_key=True, index=True)
    code_source = Column(String)
    github_url = Column(String, nullable=True)
    quality_score = Column(Float)
    total_issues = Column(Integer)
    critical_issues = Column(Integer)
    security_issues = Column(Integer)
    performance_issues = Column(Integer)
    report = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
