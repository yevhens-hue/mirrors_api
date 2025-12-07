# models.py
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Mirror(Base):
    __tablename__ = "mirrors"

    id = Column(Integer, primary_key=True, index=True)

    merchant = Column(String, index=True, nullable=False)
    country = Column(String, index=True, nullable=False)
    keyword = Column(String, index=True, nullable=False)

    source_url = Column(String, nullable=False)
    source_domain = Column(String, index=True, nullable=False)

    final_url = Column(String, nullable=True)
    final_domain = Column(String, index=True, nullable=True)

    is_redirector = Column(Boolean, default=False, nullable=False)
    is_mirror = Column(Boolean, default=False, nullable=False)
    cta_found = Column(Boolean, default=False, nullable=False)

    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "merchant",
            "country",
            "keyword",
            "source_domain",
            "final_domain",
            name="uq_mirror_unique",
        ),
    )
