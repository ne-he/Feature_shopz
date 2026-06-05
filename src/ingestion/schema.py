"""Pydantic models defining the raw e-commerce transaction schema.

Used for column-level documentation and spot-check validation of individual
rows. Full-DataFrame ingestion goes through loader.py; these models are NOT
applied row-by-row at scale (100k rows would be prohibitively slow).

Data quirks documented in PRD § 6 are recorded here via field annotations;
actual corrections (e.g. ReviewScore clipping) live in cleaner.py.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class RawTransactionRow(BaseModel):
    """Single row of the raw e-commerce transaction dataset (all 21 columns).

    Reflects the schema documented in PRD § 6. ReviewScore may arrive outside
    [1, 5] — that is an expected quirk handled by cleaner.py, not this model.
    """

    UserID: int
    UserName: str
    Age: int = Field(ge=18, le=69)
    Gender: str
    Country: str
    SignUpDate: date
    ProductID: int
    ProductName: str
    Category: str
    Price: float = Field(ge=0.0)
    PurchaseDate: date
    Quantity: int = Field(ge=1)
    TotalAmount: float = Field(ge=0.0)
    HasDiscountApplied: bool
    DiscountRate: float = Field(ge=0.0, le=1.0)
    ReviewScore: float  # raw; may be outside [1, 5] before cleaning
    ReviewText: str
    LastLogin: datetime
    SessionDuration: float = Field(ge=0.0)
    DeviceType: str
    ReferralSource: str

    @field_validator("Gender")
    @classmethod
    def gender_must_be_valid(cls, v: str) -> str:
        """Reject gender values outside the documented set."""
        valid = {"Male", "Female", "Non-Binary"}
        if v not in valid:
            raise ValueError(f"Gender must be one of {valid}, got {v!r}")
        return v

    @field_validator("Category")
    @classmethod
    def category_must_be_valid(cls, v: str) -> str:
        """Reject category values outside the documented set."""
        valid = {"Electronics", "Apparel", "Books", "Accessories"}
        if v not in valid:
            raise ValueError(f"Category must be one of {valid}, got {v!r}")
        return v
