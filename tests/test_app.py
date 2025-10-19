"""
Test suite for app.py helper functions
Tests the core functionality of the main application
"""

import time
from unittest.mock import Mock

import pytest

from app import (
    extract_with_service_async,
    get_file_type_description,
    is_valid_file_type,
    process_file_with_services_async,
)


class TestIsValidFileType:
    """Tests for is_valid_file_type function"""

    def test_valid_pdf_file(self):
        """Test that PDF files are recognized as valid"""
        mock_file = Mock()
        mock_file.name = "document.pdf"
        assert is_valid_file_type(mock_file) is True

    def test_valid_png_file(self):
        """Test that PNG files are recognized as valid"""
        mock_file = Mock()
        mock_file.name = "image.png"
        assert is_valid_file_type(mock_file) is True

    def test_valid_jpg_file(self):
        """Test that JPG files are recognized as valid"""
        mock_file = Mock()
        mock_file.name = "photo.jpg"
        assert is_valid_file_type(mock_file) is True

    def test_valid_jpeg_file(self):
        """Test that JPEG files are recognized as valid"""
        mock_file = Mock()
        mock_file.name = "photo.jpeg"
        assert is_valid_file_type(mock_file) is True

    def test_invalid_file_type(self):
        """Test that invalid file types are rejected"""
        mock_file = Mock()
        mock_file.name = "document.docx"
        assert is_valid_file_type(mock_file) is False

    def test_case_insensitive_matching(self):
        """Test that file extension matching is case insensitive"""
        mock_file = Mock()
        mock_file.name = "DOCUMENT.PDF"
        assert is_valid_file_type(mock_file) is True

    def test_none_file(self):
        """Test that None file is handled"""
        assert is_valid_file_type(None) is False

    def test_file_without_name_attribute(self):
        """Test that file without name attribute is rejected"""
        mock_file = Mock(spec=[])  # Mock without 'name' attribute
        assert is_valid_file_type(mock_file) is False

    def test_multiple_extensions(self):
        """Test file with multiple extensions"""
        mock_file = Mock()
        mock_file.name = "archive.tar.pdf"
        assert is_valid_file_type(mock_file) is True


class TestGetFileTypeDescription:
    """Tests for get_file_type_description function"""

    def test_pdf_description(self):
        """Test PDF file type description"""
        mock_file = Mock()
        mock_file.name = "document.pdf"
        assert get_file_type_description(mock_file) == "PDF Document"

    def test_png_description(self):
        """Test PNG file type description"""
        mock_file = Mock()
        mock_file.name = "image.png"
        assert get_file_type_description(mock_file) == "PNG Image"

    def test_jpg_description(self):
        """Test JPG file type description"""
        mock_file = Mock()
        mock_file.name = "photo.jpg"
        assert get_file_type_description(mock_file) == "JPEG Image"

    def test_jpeg_description(self):
        """Test JPEG file type description"""
        mock_file = Mock()
        mock_file.name = "photo.jpeg"
        assert get_file_type_description(mock_file) == "JPEG Image"

    def test_unknown_file_type(self):
        """Test unknown file type description"""
        mock_file = Mock()
        mock_file.name = "document.xyz"
        result = get_file_type_description(mock_file)
        assert "XYZ" in result

    def test_none_file(self):
        """Test None file returns unknown type"""
        assert get_file_type_description(None) == "Unknown File Type"

    def test_file_without_name_attribute(self):
        """Test file without name attribute"""
        mock_file = Mock(spec=[])
        assert get_file_type_description(mock_file) == "Unknown File Type"


class TestExtractWithServiceAsync:
    """Tests for extract_with_service_async function"""

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        """Test successful async extraction"""
        # Create mock service class
        mock_service = Mock()
        mock_service.extract.return_value = {
            "service": "TestService",
            "fields": [{"name": "tin", "value": "123-456-789"}],
        }

        mock_service_class = Mock(return_value=mock_service)
        mock_file = Mock()
        mock_file.name = "test.pdf"

        service_name, result, proc_time = await extract_with_service_async(
            "TestService", mock_service_class, mock_file
        )

        assert service_name == "TestService"
        assert "service" in result
        assert result["service"] == "TestService"
        assert proc_time >= 0  # Changed from > 0 to >= 0 for fast operations
        mock_service_class.assert_called_once_with("TestService")
        mock_service.extract.assert_called_once_with(mock_file)

    @pytest.mark.asyncio
    async def test_extraction_with_exception(self):
        """Test async extraction handles exceptions"""
        # Create mock service that raises exception
        mock_service = Mock()
        mock_service.extract.side_effect = RuntimeError("Extraction failed")

        mock_service_class = Mock(return_value=mock_service)
        mock_file = Mock()

        service_name, result, proc_time = await extract_with_service_async(
            "FailService", mock_service_class, mock_file
        )

        assert service_name == "FailService"
        assert "error" in result
        assert "Async extraction failed" in result["error"]
        assert proc_time >= 0

    @pytest.mark.asyncio
    async def test_extraction_measures_time(self):
        """Test that extraction measures processing time"""

        # Create mock service with delay
        def slow_extract(file):
            time.sleep(0.1)  # Simulate processing time
            return {"service": "SlowService"}

        mock_service = Mock()
        mock_service.extract = slow_extract

        mock_service_class = Mock(return_value=mock_service)
        mock_file = Mock()

        service_name, result, proc_time = await extract_with_service_async(
            "SlowService", mock_service_class, mock_file
        )

        assert proc_time >= 0.1  # Should take at least 0.1 seconds


class TestProcessFileWithServicesAsync:
    """Tests for process_file_with_services_async function"""

    @pytest.mark.asyncio
    async def test_process_single_service(self):
        """Test processing with a single service"""
        # Create mock service
        mock_service = Mock()
        mock_service.extract.return_value = {"service": "Service1", "data": "test"}

        mock_service_class = Mock(return_value=mock_service)
        mock_file = Mock()

        selected_services = [("Service1", mock_service_class)]

        results = await process_file_with_services_async(mock_file, selected_services)

        assert "Service1" in results
        assert results["Service1"]["service"] == "Service1"
        assert "_processing_summary" in results
        assert results["_processing_summary"]["total_services"] == 1
        assert results["_processing_summary"]["successful_services"] == 1

    @pytest.mark.asyncio
    async def test_process_multiple_services_parallel(self):
        """Test parallel processing of multiple services"""
        # Create multiple mock services
        mock_service1 = Mock()
        mock_service1.extract.return_value = {"service": "Service1"}

        mock_service2 = Mock()
        mock_service2.extract.return_value = {"service": "Service2"}

        mock_service_class1 = Mock(return_value=mock_service1)
        mock_service_class2 = Mock(return_value=mock_service2)

        mock_file = Mock()

        selected_services = [
            ("Service1", mock_service_class1),
            ("Service2", mock_service_class2),
        ]

        results = await process_file_with_services_async(mock_file, selected_services)

        assert "Service1" in results
        assert "Service2" in results
        assert "_processing_summary" in results
        assert results["_processing_summary"]["total_services"] == 2
        assert results["_processing_summary"]["successful_services"] == 2
        assert results["_processing_summary"]["failed_services"] == 0

    @pytest.mark.asyncio
    async def test_process_with_service_failures(self):
        """Test processing when some services fail"""
        # Service 1 succeeds
        mock_service1 = Mock()
        mock_service1.extract.return_value = {"service": "Service1"}

        # Service 2 fails
        mock_service2 = Mock()
        mock_service2.extract.return_value = {"service": "Service2", "error": "Failed"}

        mock_service_class1 = Mock(return_value=mock_service1)
        mock_service_class2 = Mock(return_value=mock_service2)

        mock_file = Mock()

        selected_services = [
            ("Service1", mock_service_class1),
            ("Service2", mock_service_class2),
        ]

        results = await process_file_with_services_async(mock_file, selected_services)

        assert results["_processing_summary"]["successful_services"] == 1
        assert results["_processing_summary"]["failed_services"] == 1

    @pytest.mark.asyncio
    async def test_process_with_exception(self):
        """Test processing handles unexpected exceptions"""
        # Create service that raises exception
        mock_service = Mock()
        mock_service.extract.side_effect = RuntimeError("Unexpected error")

        mock_service_class = Mock(return_value=mock_service)
        mock_file = Mock()

        selected_services = [("ErrorService", mock_service_class)]

        results = await process_file_with_services_async(mock_file, selected_services)

        assert "ErrorService" in results
        assert "error" in results["ErrorService"]
        assert results["_processing_summary"]["failed_services"] == 1

    @pytest.mark.asyncio
    async def test_process_empty_services_list(self):
        """Test processing with no services selected"""
        mock_file = Mock()
        selected_services = []

        results = await process_file_with_services_async(mock_file, selected_services)

        assert "_processing_summary" in results
        assert results["_processing_summary"]["total_services"] == 0
        assert results["_processing_summary"]["successful_services"] == 0

    @pytest.mark.asyncio
    async def test_parallel_speedup_calculation(self):
        """Test that parallel speedup is calculated correctly"""

        def slow_extract(file):
            time.sleep(0.05)
            return {"service": "SlowService"}

        mock_service1 = Mock()
        mock_service1.extract = slow_extract
        mock_service2 = Mock()
        mock_service2.extract = slow_extract

        mock_service_class1 = Mock(return_value=mock_service1)
        mock_service_class2 = Mock(return_value=mock_service2)

        mock_file = Mock()

        selected_services = [
            ("Service1", mock_service_class1),
            ("Service2", mock_service_class2),
        ]

        results = await process_file_with_services_async(mock_file, selected_services)

        # Check that parallel_speedup string is present
        assert "parallel_speedup" in results["_processing_summary"]
        speedup_str = results["_processing_summary"]["parallel_speedup"]
        assert "s avg per service" in speedup_str


class TestAsyncEdgeCases:
    """Tests for edge cases in async processing"""

    @pytest.mark.asyncio
    async def test_service_returns_none(self):
        """Test handling when service returns None"""
        mock_service = Mock()
        mock_service.extract.return_value = None

        mock_service_class = Mock(return_value=mock_service)
        mock_file = Mock()

        service_name, result, proc_time = await extract_with_service_async(
            "NoneService", mock_service_class, mock_file
        )

        assert result is None
        assert proc_time >= 0

    @pytest.mark.asyncio
    async def test_service_instantiation_fails(self):
        """Test handling when service class instantiation fails"""
        mock_service_class = Mock(side_effect=RuntimeError("Init failed"))
        mock_file = Mock()

        service_name, result, proc_time = await extract_with_service_async(
            "BadService", mock_service_class, mock_file
        )

        assert "error" in result
        assert "Async extraction failed" in result["error"]

    @pytest.mark.asyncio
    async def test_concurrent_execution_time(self):
        """Test that parallel execution is actually faster than sequential"""

        def timed_extract(file):
            time.sleep(0.1)
            return {"service": "TimedService"}

        # Create 3 services
        services = []
        for i in range(3):
            mock_service = Mock()
            mock_service.extract = timed_extract
            mock_service_class = Mock(return_value=mock_service)
            services.append((f"Service{i}", mock_service_class))

        mock_file = Mock()

        start = time.time()
        results = await process_file_with_services_async(mock_file, services)
        elapsed = time.time() - start

        # With parallel execution, 3 services with 0.1s each should take ~0.1s
        # not 0.3s (sequential). Allow some overhead.
        assert elapsed < 0.25  # Should be much less than 3 * 0.1 = 0.3s
        assert results["_processing_summary"]["successful_services"] == 3
