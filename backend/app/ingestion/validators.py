from pydantic import BaseModel, ConfigDict, Field, field_validator
from decimal import Decimal
from datetime import datetime
from typing import Any, Optional

class ImportResult(BaseModel):
    model_config = ConfigDict(strict=False)
    
    records_received: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    duplicates: int = 0
    validation_errors: list[dict[str, Any]] = Field(default_factory=list)

class BaseImportRecord(BaseModel):
    model_config = ConfigDict(strict=False)
    
    source_id: str
    source_system: str

class PaymentImportRecord(BaseImportRecord):
    amount: Decimal = Field(ge=0)
    currency: str = "INR"
    status: str
    method: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None
    payment_timestamp: datetime
    order_source_id: Optional[str] = None
    fee: Optional[Decimal] = Field(default=None, ge=0)
    tax: Optional[Decimal] = Field(default=None, ge=0)
    
    @field_validator("payment_timestamp", mode="before")
    def parse_timestamp(cls, value: Any) -> Any:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        return value

class OrderImportRecord(BaseImportRecord):
    amount: Decimal = Field(ge=0)
    currency: str = "INR"
    status: str
    order_timestamp: datetime
    
    @field_validator("order_timestamp", mode="before")
    def parse_timestamp(cls, value: Any) -> Any:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        return value

class SettlementImportRecord(BaseImportRecord):
    amount: Decimal
    currency: str = "INR"
    status: str
    settlement_timestamp: datetime
    fee: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    utr: Optional[str] = None
    
    @field_validator("settlement_timestamp", mode="before")
    def parse_timestamp(cls, value: Any) -> Any:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        return value

class RefundImportRecord(BaseImportRecord):
    amount: Decimal = Field(ge=0)
    currency: str = "INR"
    status: str
    payment_source_id: str
    refund_timestamp: datetime
    
    @field_validator("refund_timestamp", mode="before")
    def parse_timestamp(cls, value: Any) -> Any:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        return value

class ChargebackImportRecord(BaseImportRecord):
    amount: Decimal = Field(ge=0)
    currency: str = "INR"
    status: str
    payment_source_id: str
    reason_code: Optional[str] = None
    chargeback_timestamp: datetime
    
    @field_validator("chargeback_timestamp", mode="before")
    def parse_timestamp(cls, value: Any) -> Any:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        return value

class LedgerEntryImportRecord(BaseImportRecord):
    amount: Decimal
    currency: str = "INR"
    type: str # debit/credit
    entry_timestamp: datetime
    description: Optional[str] = None
    
    @field_validator("entry_timestamp", mode="before")
    def parse_timestamp(cls, value: Any) -> Any:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        return value
