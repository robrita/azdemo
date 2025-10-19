"""Pydantic schemas for GPT Vision document extraction.

Defines structured models used for parsing Azure OpenAI Vision responses.
"""

from pydantic import BaseModel, Field


class DocSchema(BaseModel):
    """Structured extraction model for BIR 2303 tax documents.

    Fields map to the standardized JSON output consumed by the Streamlit app.
    All fields are optional because documents may have missing values. Dates
    are expected in MM/DD/YYYY format when present.
    """

    language: str | None = Field(None, description="The language of the document.")
    summary: str | None = Field(None, description="A brief summary of the document in English.")
    tin: str | None = Field(
        None,
        description=(
            "The taxpayer identification number (TIN) in format "
            "XXX-XXX-XXX-XXXXX or XXX-XXX-XXX-XXXX or XXX-XXX-XXX-XXX."
        ),
    )
    taxpayerName: str | None = Field(
        None,
        description=(
            "The full name of the taxpayer or business entity as registered with the tax authority."
        ),
    )
    registeredDate: str | None = Field(
        None, description="The date the TIN was issued or registered in MM/DD/YYYY format."
    )
    registeredAddress: str | None = Field(
        None, description="The complete registered address of the taxpayer or business."
    )
    tradeName: str | None = Field(
        None, description="The registered trade name or business name of the taxpayer."
    )
    businessType: str | None = Field(
        None, description="The line of business or business activities"
    )


__all__ = ["DocSchema"]
