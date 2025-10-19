"""Unit tests for Demo Form Pre-Fill page."""

import sys

import pytest

sys.path.append("..")
from pages.pg2_Demo_Form_PreFill import (
    SERVICE_CONFIG,
    extract_field_value,
    is_valid_file_type,
)


class TestFileValidation:
    """Test file type validation."""

    @pytest.mark.unit
    def test_valid_pdf_file(self, mock_pdf_file):
        """Test that PDF files are recognized as valid."""
        assert is_valid_file_type(mock_pdf_file) is True

    @pytest.mark.unit
    def test_valid_image_file(self, sample_image_file):
        """Test that image files are recognized as valid."""
        assert is_valid_file_type(sample_image_file) is True

    @pytest.mark.unit
    def test_invalid_file_type(self):
        """Test that invalid file types are rejected."""

        class MockInvalidFile:
            name = "document.txt"

        assert is_valid_file_type(MockInvalidFile()) is False

    @pytest.mark.unit
    def test_none_file(self):
        """Test that None file is handled gracefully."""
        assert is_valid_file_type(None) is False


class TestFieldExtraction:
    """Test field value extraction from results."""

    @pytest.mark.unit
    def test_extract_existing_field(self):
        """Test extracting a field that exists in the result."""
        extraction_result = {
            "service": "Test-Service",
            "documents": [
                {
                    "fields": {
                        "tin": {"content": "123-456-789-0000", "confidence": 0.95},
                        "taxpayerName": {"content": "John Doe", "confidence": 0.98},
                    }
                }
            ],
        }

        assert extract_field_value(extraction_result, "tin") == "123-456-789-0000"
        assert extract_field_value(extraction_result, "taxpayerName") == "John Doe"

    @pytest.mark.unit
    def test_extract_missing_field(self):
        """Test extracting a field that doesn't exist returns empty string."""
        extraction_result = {
            "service": "Test-Service",
            "documents": [{"fields": {"tin": {"content": "123-456-789-0000"}}}],
        }

        assert extract_field_value(extraction_result, "nonexistent_field") == ""

    @pytest.mark.unit
    def test_extract_from_error_result(self):
        """Test extracting from an error result returns empty string."""
        extraction_result = {"service": "Test-Service", "error": "Extraction failed"}

        assert extract_field_value(extraction_result, "tin") == ""

    @pytest.mark.unit
    def test_extract_no_documents(self):
        """Test extracting when no documents in result."""
        extraction_result = {"service": "Test-Service", "documents": []}

        assert extract_field_value(extraction_result, "tin") == ""

    @pytest.mark.unit
    def test_extract_with_value_fallback(self):
        """Test extraction falls back to 'value' if 'content' is missing."""
        extraction_result = {
            "service": "Test-Service",
            "documents": [{"fields": {"tin": {"value": "123-456-789-0000", "confidence": 0.95}}}],
        }

        assert extract_field_value(extraction_result, "tin") == "123-456-789-0000"


class TestServiceConfiguration:
    """Test service configuration mapping."""

    @pytest.mark.unit
    def test_service_config_exists(self):
        """Test that SERVICE_CONFIG is properly defined."""
        assert isinstance(SERVICE_CONFIG, dict)
        assert len(SERVICE_CONFIG) > 0

    @pytest.mark.unit
    def test_service_config_structure(self):
        """Test that each service config has correct structure."""
        for display_name, (service_name, service_class) in SERVICE_CONFIG.items():
            assert isinstance(display_name, str)
            assert isinstance(service_name, str)
            assert service_class is not None
            # Service name should not be empty
            assert len(service_name) > 0

    @pytest.mark.unit
    def test_all_expected_services_present(self):
        """Test that all expected services are in the config."""
        expected_services = [
            "Document Intelligence - Template",
            "Document Intelligence - Neural",
            "Content Understanding",
            "Mistral Document AI",
            "GPT-4.1 for Vision",
            "GPT-5 for Vision",
        ]

        for service in expected_services:
            assert service in SERVICE_CONFIG, f"Missing service: {service}"
