from typing import Any


def get_mistral_json_schema() -> dict[str, Any]:
    """
    Return the JSON schema object for Mistral Document AI extraction.
    """
    return {
        "name": "bir_document_extraction",
        "description": "Extract structured information from BIR (Bureau of Internal Revenue) tax documents",
        "schema": {
            "properties": {
                "language": {
                    "title": "Language",
                    "type": "string",
                    "description": "The language of the document.",
                },
                "summary": {
                    "title": "Summary",
                    "type": "string",
                    "description": "A brief summary of the document in English.",
                },
                "tin": {
                    "title": "TIN Number",
                    "type": "string",
                    "description": "The taxpayer identification number (TIN) in format XXX-XXX-XXX-XXXXX or XXX-XXX-XXX-XXXX or XXX-XXX-XXX-XXX.",
                },
                "taxpayerName": {
                    "title": "Taxpayer Name",
                    "type": "string",
                    "description": "The full name of the taxpayer or business entity as registered with the tax authority.",
                },
                "registeredDate": {
                    "title": "Registered Date",
                    "type": "string",
                    "description": "The date the TIN was issued or registered in MM/DD/YYYY format.",
                },
                "registeredAddress": {
                    "title": "Registered Address",
                    "type": "string",
                    "description": "The complete registered address of the taxpayer or business.",
                },
                "tradeName": {
                    "title": "Trade Name",
                    "type": "string",
                    "description": "The registered trade name or business name of the taxpayer.",
                },
                "businessType": {
                    "title": "Business Type",
                    "type": "string",
                    "description": "The line of business or business activities",
                },
            }
        },
    }
