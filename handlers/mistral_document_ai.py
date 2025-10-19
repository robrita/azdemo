import base64
import json
import logging
import os
import sys
import time
from typing import Any

import requests

sys.path.append("..")
from schemas.mistral_schema import get_mistral_json_schema
from utils import save_extraction_to_json

# Configure logging
logger = logging.getLogger(__name__)


class MistralDocumentAI:
    """
    Handler for Mistral Document AI service
    Uses Mistral's AI models for document understanding and extraction
    Supports: Images (JPEG, PNG) and PDF documents
    """

    def __init__(self, service_name=None):
        self.service_name = service_name or "Mistral Document AI"
        # Initialize Mistral Document AI configuration
        self.endpoint = os.environ.get("AZURE_MISTRAL_DOCUMENT_AI_ENDPOINT")
        self.key = os.environ.get("AZURE_MISTRAL_DOCUMENT_AI_KEY")

        if not self.endpoint or not self.key:
            logger.error(f"Missing Mistral Document AI credentials for {self.service_name}")

        # Request headers
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.key}",
        }

    def extract(self, uploaded_file) -> dict[str, Any]:
        """
        Extract data using Mistral Document AI service

        Args:
            uploaded_file: Streamlit uploaded file object

        Returns:
            Dict containing extracted data
        """
        logger.info(f"Mistral Document AI extraction started: {uploaded_file.name}")
        try:
            # Start timing
            start_time = time.time()

            # Read file content
            file_bytes = uploaded_file.getvalue()
            file_name = uploaded_file.name
            file_type = uploaded_file.type

            # Encode document to base64
            encoded_document = base64.b64encode(file_bytes).decode("utf-8")

            # Determine MIME type based on file type
            mime_type = "image/jpeg"  # Default
            if "png" in file_type.lower():
                mime_type = "image/png"
            elif "pdf" in file_type.lower():
                mime_type = "application/pdf"
            elif "jpg" in file_type.lower() or "jpeg" in file_type.lower():
                mime_type = "image/jpeg"

            # Determine document type and URL key based on file type
            if "pdf" in file_type.lower():
                doc_type = "document_url"
                doc_url_key = "document_url"
            else:
                doc_type = "image_url"
                doc_url_key = "image_url"

            # Retrieve JSON schema via helper function in schemas/mistral_schema.py
            json_schema = get_mistral_json_schema()

            document_annotation_payload = {
                "model": "mistral-document-ai-2505",
                "document": {
                    "type": doc_type,
                    doc_url_key: f"data:{mime_type};base64,{encoded_document}",
                },
                "include_image_base64": "true",
                "document_annotation_format": {
                    "type": "json_schema",
                    "json_schema": json_schema,
                },
            }

            # Make API request to Mistral Document AI
            # Increased timeout for PDF processing which may take longer
            timeout_duration = 120 if "pdf" in file_type.lower() else 60

            logger.debug("Analyzing document with Mistral Document AI...")
            response = requests.post(
                url=self.endpoint,
                json=document_annotation_payload,
                headers=self.headers,
                timeout=timeout_duration,
            )
            response.raise_for_status()

            # Calculate processing time
            processing_time = time.time() - start_time

            # Parse response
            response_data = response.json()

            # Extract document annotation
            document_annotation = None
            if "document_annotation" in response_data:
                document_annotation = json.loads(response_data["document_annotation"])

            # Build extracted data structure
            extracted_data = {
                "service": self.service_name,
                "file_info": {"name": file_name, "type": file_type, "size": len(file_bytes)},
                "model_info": {"model_id": "mistral-document-ai-2505", "api_version": "2025.05"},
                "documents": [],
            }

            # Process extracted fields from document annotation
            if document_annotation and "properties" in document_annotation:
                properties = document_annotation["properties"]

                # Build fields dictionary for save_extraction_to_json
                fields_dict = {}
                overall_confidence = 0.0

                # Map the extracted properties to fields with confidence scores
                # Mistral doesn't provide per-field confidence, so we set it to 0
                for field_name, field_value in properties.items():
                    if field_value:  # Only include fields with values
                        fields_dict[field_name] = {
                            "content": str(field_value),
                            "confidence": 0.0,
                            "type": "string",
                        }

                # Create document entry
                doc_data = {
                    "document_number": 1,
                    "doc_type": "BIR Tax Document",
                    "confidence": round(overall_confidence, 3),
                    "fields": {},
                }

                # Add fields to document data for display
                for field_name, field_info in fields_dict.items():
                    doc_data["fields"][field_name] = {
                        "type": field_info["type"],
                        "content": field_info["content"],
                        "confidence": field_info["confidence"],
                    }

                extracted_data["documents"].append(doc_data)

                # Save results to JSON file using common utility function
                if fields_dict:
                    save_extraction_to_json(
                        file_name,
                        self.service_name,
                        pages_count=1,  # Mistral processes single images
                        fields=fields_dict,
                        overall_confidence=overall_confidence,
                        processing_time=processing_time,
                    )

            # Add processing summary
            extracted_data["processing_info"] = {
                "pages_processed": 1,
                "documents_found": len(extracted_data["documents"]),
                "processing_time_seconds": round(processing_time, 3),
            }

            return extracted_data

        except requests.exceptions.RequestException as e:
            import traceback

            logger.error(
                f"Mistral error: {uploaded_file.name if 'uploaded_file' in locals() else 'unknown'} "
                f"| {self.service_name} | {str(e)}",
                exc_info=True,
            )
            return {
                "service": self.service_name,
                "error": f"Mistral Document AI API request failed: {str(e)}",
                "error_details": traceback.format_exc(),
                "file_info": {
                    "name": uploaded_file.name if uploaded_file else "Unknown",
                    "type": uploaded_file.type if uploaded_file else "Unknown",
                },
            }
        except Exception as e:
            import traceback

            logger.error(
                f"Mistral error: {uploaded_file.name if 'uploaded_file' in locals() else 'unknown'} "
                f"| {self.service_name} | {str(e)}",
                exc_info=True,
            )
            return {
                "service": self.service_name,
                "error": f"Mistral Document AI extraction failed: {str(e)}",
                "error_details": traceback.format_exc(),
                "file_info": {
                    "name": uploaded_file.name if uploaded_file else "Unknown",
                    "type": uploaded_file.type if uploaded_file else "Unknown",
                },
            }
