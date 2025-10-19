import os
import sys
import time
from typing import Any

import requests
import streamlit as st

sys.path.append("..")
from utils import save_extraction_to_json


class ContentUnderstanding:
    """
    Handler for Azure Content Understanding service
    Uses Azure Content Understanding SDK for document extraction
    """

    def __init__(self, service_name=None):
        self.service_name = service_name or "Content-Understanding"
        # Initialize Azure Content Understanding client settings
        self.endpoint = os.environ.get("AZURE_CONTENT_UNDERSTANDING_ENDPOINT")
        self.subscription_key = os.environ.get("AZURE_CONTENT_UNDERSTANDING_SUBSCRIPTION_KEY")
        self.analyzer_id = os.environ.get("AZURE_CONTENT_UNDERSTANDING_ANALYZER_ID")
        self.api_version = os.environ.get(
            "AZURE_CONTENT_UNDERSTANDING_API_VERSION", "2025-05-01-preview"
        )

    def _get_headers(self) -> dict[str, str]:
        """Build request headers with authentication"""
        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "x-ms-useragent": "content-understanding-document-extraction",
        }
        return headers

    def _begin_analyze(self, file_bytes: bytes) -> requests.Response:
        """
        Start document analysis operation

        Args:
            file_bytes: Document content as bytes

        Returns:
            Response object with operation location
        """
        url = f"{self.endpoint}/contentunderstanding/analyzers/{self.analyzer_id}:analyze?api-version={self.api_version}&stringEncoding=utf16"

        headers = self._get_headers()
        headers["Content-Type"] = "application/octet-stream"

        response = requests.post(url=url, headers=headers, data=file_bytes)
        response.raise_for_status()

        return response

    def _poll_result(
        self, operation_location: str, timeout_seconds: int = 120, polling_interval_seconds: int = 2
    ) -> dict[str, Any]:
        """
        Poll for analysis result until completion or timeout

        Args:
            operation_location: URL to poll for results
            timeout_seconds: Maximum wait time
            polling_interval_seconds: Delay between polls

        Returns:
            Analysis result as dict
        """
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        start_time = time.time()
        while True:
            elapsed_time = time.time() - start_time

            if elapsed_time > timeout_seconds:
                raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds")

            response = requests.get(operation_location, headers=headers)
            response.raise_for_status()
            result = response.json()

            status = result.get("status", "").lower()
            if status == "succeeded":
                return result
            if status == "failed":
                raise RuntimeError(f"Analysis failed: {result}")

            time.sleep(polling_interval_seconds)

    def extract(self, uploaded_file) -> dict[str, Any]:
        """
        Extract data using Content Understanding service

        Args:
            uploaded_file: Streamlit uploaded file object

        Returns:
            Dict containing extracted data
        """
        try:
            # Start timing
            start_time = time.time()

            # Read file content
            file_bytes = uploaded_file.getvalue()
            file_name = uploaded_file.name

            # Check if credentials are available
            if not self.endpoint or not self.subscription_key or not self.analyzer_id:
                return {
                    "service": self.service_name,
                    "error": "Content Understanding credentials not configured. Please set AZURE_CONTENT_UNDERSTANDING_ENDPOINT, AZURE_CONTENT_UNDERSTANDING_SUBSCRIPTION_KEY, and AZURE_CONTENT_UNDERSTANDING_ANALYZER_ID in .env file",
                    "file_info": {"name": file_name, "type": uploaded_file.type},
                }

            # Begin analyze document operation
            with st.spinner("Analyzing document with Content Understanding..."):
                response = self._begin_analyze(file_bytes)
                operation_location = response.headers.get("operation-location", "")

                if not operation_location:
                    raise ValueError("Operation location not found in response headers")

                # Poll for result
                result = self._poll_result(
                    operation_location, timeout_seconds=120, polling_interval_seconds=2
                )

            # Calculate processing time
            processing_time = time.time() - start_time

            # Extract data from result
            extracted_data = {
                "service": self.service_name,
                "file_info": {
                    "name": file_name,
                    "type": uploaded_file.type,
                    "size": len(file_bytes),
                },
                "operation_info": {
                    "id": result.get("id", "N/A"),
                    "status": result.get("status", "N/A"),
                },
                "documents": [],
            }

            # Process analysis result
            result_data = result.get("result", {})
            contents = result_data.get("contents", [])

            if contents:
                for idx, content in enumerate(contents):
                    fields = content.get("fields", {})

                    doc_data = {
                        "document_number": idx + 1,
                        "doc_type": content.get("kind", "document"),
                        "confidence": 0.0,  # Content Understanding doesn't provide overall confidence
                        "page_range": {
                            "start": content.get("startPageNumber", 1),
                            "end": content.get("endPageNumber", 1),
                        },
                        "fields": {},
                    }

                    # Extract fields with their values
                    for field_name, field_data in fields.items():
                        if isinstance(field_data, dict):
                            doc_data["fields"][field_name] = {
                                "type": field_data.get("type", "unknown"),
                                "content": field_data.get("valueString", str(field_data)),
                                "confidence": 0.0,  # Content Understanding doesn't provide field-level confidence
                            }

                    extracted_data["documents"].append(doc_data)

            # Add processing summary
            extracted_data["processing_info"] = {
                "analyzer_id": result_data.get("analyzerId", "N/A"),
                "api_version": result_data.get("apiVersion", "N/A"),
                "created_at": result_data.get("createdAt", "N/A"),
                "warnings": result_data.get("warnings", []),
            }

            # Save results to JSON file using common utility function
            if contents and len(contents) > 0:
                # Use the first content's fields for scoring
                first_content = contents[0]
                fields = first_content.get("fields", {})
                pages_count = len(first_content.get("pages", []))

                # Build fields dictionary for save_extraction_to_json
                # Following the same pattern as mistral_document_ai.py
                fields_dict = {}
                overall_confidence = 0.0

                # Map the extracted properties to fields with confidence scores
                for field_name, field_data in fields.items():
                    if isinstance(field_data, dict):
                        value = field_data.get("valueString", str(field_data))
                        field_type = field_data.get("type", "string")

                        if value:  # Only include fields with values
                            fields_dict[field_name] = {
                                "content": value,
                                "confidence": 0.0,  # Content Understanding doesn't provide confidence
                                "type": field_type,
                            }

                # Save extraction results
                if fields_dict:
                    save_extraction_to_json(
                        file_name,
                        self.service_name,
                        pages_count,
                        fields_dict,
                        overall_confidence=overall_confidence,
                        processing_time=processing_time,
                    )

            return extracted_data

        except Exception as e:
            import traceback

            return {
                "service": self.service_name,
                "error": f"Content Understanding extraction failed: {str(e)}",
                "error_details": traceback.format_exc(),
                "file_info": {
                    "name": uploaded_file.name if uploaded_file else "Unknown",
                    "type": uploaded_file.type if uploaded_file else "Unknown",
                },
            }
