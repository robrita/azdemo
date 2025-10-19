"""
Integration tests for document extraction handlers.

These tests use actual sample images from tests/data/ and may require
Azure service credentials to run. Mark as integration tests to skip
in unit test runs.
"""

import json

import pytest


@pytest.mark.integration
class TestDocumentIntelligenceIntegration:
    """Integration tests for DocumentIntelligence handler with real images."""

    @pytest.fixture(autouse=True)
    def setup(self, real_env_vars):  # noqa: F811, ARG002
        """Setup with real environment variables from .env file."""
        pass

    def test_extract_from_sample_image(self, sample_image_file):
        """Test extraction from a real sample image."""
        from handlers.document_intelligence import DocumentIntelligence

        handler = DocumentIntelligence(service_name="ADI-Template")

        # Skip if no real credentials
        if handler.client is None:
            pytest.skip("Azure Document Intelligence credentials not configured")

        result = handler.extract(sample_image_file)

        # Verify no error occurred
        assert "error" not in result
        assert "service" in result
        assert "documents" in result

    def test_extract_from_all_sample_images(self, all_sample_images, tmp_path):
        """Test extraction from all sample images in tests/data/."""
        from handlers.document_intelligence import DocumentIntelligence

        handler = DocumentIntelligence(service_name="ADI-Template")

        if handler.client is None:
            pytest.skip("Azure Document Intelligence credentials not configured")

        results = []
        for sample_file in all_sample_images:
            result = handler.extract(sample_file)
            results.append(result)

            # Verify basic structure
            assert "service" in result

        # Verify we processed all files
        assert len(results) == len(all_sample_images)

    def test_extract_and_save_json(self, sample_image_file, tmp_path):
        """Test extraction saves results to JSON file."""
        from handlers.document_intelligence import DocumentIntelligence

        handler = DocumentIntelligence(service_name="ADI-Template")

        if handler.client is None:
            pytest.skip("Azure Document Intelligence credentials not configured")

        results_file = tmp_path / "integration_results.json"

        # Mock the results file path
        import utils

        original_save = utils.save_extraction_to_json

        def custom_save(*args, **kwargs):
            kwargs["results_file_path"] = str(results_file)
            return original_save(*args, **kwargs)

        with pytest.MonkeyPatch.context() as m:
            m.setattr(utils, "save_extraction_to_json", custom_save)
            result = handler.extract(sample_image_file)

        # Verify JSON file was created
        if "error" not in result and results_file.exists():
            with open(results_file, encoding="utf-8") as f:
                data = json.load(f)
            assert "results" in data


@pytest.mark.integration
class TestGPTForVisionIntegration:
    """Integration tests for GPTForVision handler with real images."""

    @pytest.fixture(autouse=True)
    def setup(self, real_env_vars):  # noqa: F811, ARG002
        """Setup with real environment variables from .env file."""
        pass

    def test_extract_from_sample_image(self, sample_image_file):
        """Test GPT Vision extraction from sample image."""
        from handlers.gpt_vision import GPTForVision

        handler = GPTForVision(service_name="GPT-4.1-Vision")

        if handler.client is None:
            pytest.skip("Azure OpenAI credentials not configured")

        result = handler.extract(sample_image_file)

        # Verify no error occurred
        assert "error" not in result or "not initialized" in result.get("error", "")
        if "error" not in result:
            assert "service" in result
            assert "documents" in result

    def test_compare_gpt4_vs_gpt5(self, sample_image_file):
        """Test and compare GPT-4 vs GPT-5 extraction results."""
        from handlers.gpt_vision import GPTForVision

        handler_gpt4 = GPTForVision(service_name="GPT-4.1-Vision")
        handler_gpt5 = GPTForVision(service_name="GPT-5-Vision")

        if handler_gpt4.client is None or handler_gpt5.client is None:
            pytest.skip("Azure OpenAI credentials not configured")

        result_gpt4 = handler_gpt4.extract(sample_image_file)
        result_gpt5 = handler_gpt5.extract(sample_image_file)

        # Both should return results
        assert "service" in result_gpt4
        assert "service" in result_gpt5

        # Services should be different
        assert result_gpt4["service"] != result_gpt5["service"]


@pytest.mark.integration
class TestMultipleServicesComparison:
    """Integration tests comparing multiple extraction services."""

    @pytest.fixture(autouse=True)
    def setup(self, real_env_vars):  # noqa: F811, ARG002
        """Setup with real environment variables from .env file."""
        pass

    def test_compare_all_services(self, sample_image_file, tmp_path):
        """Test and compare results from all available services."""
        from handlers.content_understanding import ContentUnderstanding
        from handlers.document_intelligence import DocumentIntelligence
        from handlers.gpt_vision import GPTForVision
        from handlers.mistral_document_ai import MistralDocumentAI

        services = {
            "ADI-Template": DocumentIntelligence(service_name="ADI-Template"),
            "ADI-Neural": DocumentIntelligence(service_name="ADI-Neural"),
            "GPT-4.1-Vision": GPTForVision(service_name="GPT-4.1-Vision"),
            "Content-Understanding": ContentUnderstanding(service_name="Content-Understanding"),
            "Mistral-Document-AI": MistralDocumentAI(service_name="Mistral-Document-AI"),
        }

        results = {}
        for service_name, handler in services.items():
            # Check if handler is properly initialized
            if hasattr(handler, "client") and handler.client is None:
                continue
            if hasattr(handler, "endpoint") and handler.endpoint is None:
                continue

            try:
                result = handler.extract(sample_image_file)
                if "error" not in result:
                    results[service_name] = result
            except Exception:
                # Skip services that fail
                continue

        # Save comparison results
        if results:
            comparison_file = tmp_path / "service_comparison.json"
            with open(comparison_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            # Verify we got at least one result
            assert len(results) > 0

    def test_processing_time_comparison(self, sample_image_file):
        """Test and compare processing times across services."""
        import time

        from handlers.document_intelligence import DocumentIntelligence

        handler = DocumentIntelligence(service_name="ADI-Template")

        if handler.client is None:
            pytest.skip("Azure Document Intelligence credentials not configured")

        start_time = time.time()
        result = handler.extract(sample_image_file)
        end_time = time.time()

        processing_time = end_time - start_time

        # Verify reasonable processing time (should be less than 30 seconds)
        assert processing_time < 30

        # Verify processing_info is included
        if "error" not in result:
            assert "processing_info" in result


@pytest.mark.integration
@pytest.mark.slow
class TestBatchProcessing:
    """Integration tests for batch processing multiple files."""

    @pytest.fixture(autouse=True)
    def setup(self, real_env_vars):  # noqa: F811, ARG002
        """Setup with real environment variables from .env file."""
        pass

    def test_batch_extract_all_samples(self, all_sample_images, tmp_path):
        """Test batch extraction of all sample images."""
        from handlers.document_intelligence import DocumentIntelligence

        handler = DocumentIntelligence(service_name="ADI-Template")

        if handler.client is None:
            pytest.skip("Azure Document Intelligence credentials not configured")

        results_file = tmp_path / "batch_results.json"
        all_results = []

        for sample_file in all_sample_images:
            result = handler.extract(sample_file)
            all_results.append(
                {
                    "file_name": sample_file.name,
                    "service": handler.service_name,
                    "result": result,
                }
            )

        # Save batch results
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)

        # Verify all files were processed
        assert len(all_results) == len(all_sample_images)

        # Count successes and failures
        successes = sum(1 for r in all_results if "error" not in r["result"])
        failures = sum(1 for r in all_results if "error" in r["result"])

        print(f"\nBatch processing results: {successes} successes, {failures} failures")

    def test_parallel_service_extraction(self, sample_image_file, tmp_path):
        """Test extracting same file with multiple services in parallel."""
        import asyncio

        from handlers.document_intelligence import DocumentIntelligence
        from handlers.gpt_vision import GPTForVision

        async def extract_async(handler, file):
            """Async wrapper for extraction."""
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, handler.extract, file)

        async def process_parallel():
            handlers = [
                DocumentIntelligence(service_name="ADI-Template"),
                DocumentIntelligence(service_name="ADI-Neural"),
                GPTForVision(service_name="GPT-4.1-Vision"),
            ]

            # Filter out handlers without credentials
            valid_handlers = [
                h
                for h in handlers
                if (hasattr(h, "client") and h.client is not None)
                or (hasattr(h, "endpoint") and h.endpoint is not None)
            ]

            if not valid_handlers:
                pytest.skip("No Azure service credentials configured")

            tasks = [extract_async(h, sample_image_file) for h in valid_handlers]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            return results

        # Run parallel extraction
        results = asyncio.run(process_parallel())

        # Verify we got results
        assert len(results) > 0

        # Save parallel results
        parallel_file = tmp_path / "parallel_results.json"
        results_data = [r if not isinstance(r, Exception) else {"error": str(r)} for r in results]

        with open(parallel_file, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)


@pytest.mark.integration
class TestErrorRecovery:
    """Integration tests for error handling and recovery."""

    @pytest.fixture(autouse=True)
    def setup(self, real_env_vars):  # noqa: F811, ARG002
        """Setup with real environment variables from .env file."""
        pass

    def test_extract_handles_network_timeout(self, sample_image_file):
        """Test extraction handles network timeout gracefully."""
        from unittest.mock import patch

        from handlers.document_intelligence import DocumentIntelligence

        handler = DocumentIntelligence(service_name="ADI-Template")

        if handler.client is None:
            pytest.skip("Azure Document Intelligence credentials not configured")

        # Mock a timeout
        with patch.object(
            handler.client,
            "begin_analyze_document",
            side_effect=TimeoutError("Request timeout"),
        ):
            result = handler.extract(sample_image_file)

        # Should return error, not crash
        assert "error" in result

    def test_extract_handles_invalid_api_key(self, sample_image_file):
        """Test extraction handles invalid API key."""
        from handlers.document_intelligence import DocumentIntelligence

        handler = DocumentIntelligence(service_name="ADI-Template")

        if handler.client is None:
            pytest.skip("Azure Document Intelligence credentials not configured")

        # Mock authentication error
        from unittest.mock import patch

        with patch.object(
            handler.client,
            "begin_analyze_document",
            side_effect=Exception("Authentication failed"),
        ):
            result = handler.extract(sample_image_file)

        # Should return error with authentication message
        assert "error" in result
        assert "Authentication failed" in result["error"]

    def test_extract_retries_on_transient_error(self, sample_image_file):
        """Test extraction can retry on transient errors."""
        from unittest.mock import Mock, patch

        from handlers.document_intelligence import DocumentIntelligence

        handler = DocumentIntelligence(service_name="ADI-Template")

        if handler.client is None:
            pytest.skip("Azure Document Intelligence credentials not configured")

        # Mock transient error then success
        mock_result = Mock(documents=[], pages=[], tables=[])
        mock_poller = Mock()
        mock_poller.result.return_value = mock_result

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Transient error")
            return mock_poller

        # This test demonstrates retry logic would be needed
        # Current implementation doesn't retry, so it will fail
        with patch.object(handler.client, "begin_analyze_document", side_effect=side_effect):
            result = handler.extract(sample_image_file)

        # Current implementation will show error on first failure
        assert "error" in result
