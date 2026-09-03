"""Merchant model."""
import uuid
from sqlalchemy import String, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from .base import BaseModel


class Merchant(BaseModel):
    """Represents a merchant using the reconciliation system."""
    __tablename__ = "merchants"

    name: Mapped[str] = mapped_column(String, nullable=False)
    razorpay_account_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    business_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
