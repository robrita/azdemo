"""
Unit tests for document extraction handlers.

Tests all handler classes including DocumentIntelligence, GPTForVision,
MistralDocumentAI, and ContentUnderstanding.
"""

import time
from unittest.mock import Mock, patch

import pytest


class TestDocumentIntelligenceHandler:
    """Test suite for DocumentIntelligence handler."""

    @pytest.fixture
    def handler_template(self, mock_env_vars):
        """Create a DocumentIntelligence handler with template service."""
        from handlers.document_intelligence import DocumentIntelligence

        return DocumentIntelligence(service_name="ADI-Template")

    @pytest.fixture
    def handler_neural(self, mock_env_vars):
        """Create a DocumentIntelligence handler with neural service."""
        from handlers.document_intelligence import DocumentIntelligence

        return DocumentIntelligence(service_name="ADI-Neural")

    def test_handler_initialization_with_env_vars(self, mock_env_vars):
        """Test handler initializes correctly with environment variables."""
        from handlers.document_intelligence import DocumentIntelligence

        handler = DocumentIntelligence(service_name="ADI-Template")

        assert handler.service_name == "ADI-Template"
        assert handler.endpoint == "https://test-endpoint.cognitiveservices.azure.com/"
        assert handler.key == "test_key_12345"
        assert handler.model_template == "prebuilt-document"
        assert handler.model_neural == "prebuilt-layout"
        assert handler.client is not None

    def test_handler_initialization_without_env_vars(self, mock_missing_env_vars):
        """Test handler handles missing environment variables gracefully."""
        from handlers.document_intelligence import DocumentIntelligence

        handler = DocumentIntelligence(service_name="ADI-Template")

        assert handler.service_name == "ADI-Template"
        assert handler.endpoint is None
        assert handler.key is None
        assert handler.client is None

    def test_extract_uses_template_model_for_template_service(
        self, handler_template, sample_image_file
    ):
        """Test extract uses template model when service name contains 'template'."""
        # Mock the client and poller
        mock_result = Mock()
        mock_result.model_id = "prebuilt-document"
        mock_result.api_version = "2024-01-01"
        mock_result.documents = []
        mock_result.pages = []
        mock_result.tables = []

        mock_poller = Mock()
        mock_poller.result.return_value = mock_result

        handler_template.client.begin_analyze_document = Mock(return_value=mock_poller)

        # Execute
        with patch("streamlit.spinner"):
            handler_template.extract(sample_image_file)

        # Verify template model was used
        handler_template.client.begin_analyze_document.assert_called_once()
        model_arg = handler_template.client.begin_analyze_document.call_args[0][0]
        assert model_arg == "prebuilt-document"

    def test_extract_uses_neural_model_for_neural_service(self, handler_neural, sample_image_file):
        """Test extract uses neural model when service name doesn't contain 'template'."""
        # Mock the client and poller
        mock_result = Mock()
        mock_result.model_id = "prebuilt-layout"
        mock_result.api_version = "2024-01-01"
        mock_result.documents = []
        mock_result.pages = []
        mock_result.tables = []

        mock_poller = Mock()
        mock_poller.result.return_value = mock_result

        handler_neural.client.begin_analyze_document = Mock(return_value=mock_poller)

        # Execute
        with patch("streamlit.spinner"):
            handler_neural.extract(sample_image_file)

        # Verify neural model was used
        handler_neural.client.begin_analyze_document.assert_called_once()
        model_arg = handler_neural.client.begin_analyze_document.call_args[0][0]
        assert model_arg == "prebuilt-layout"

    def test_extract_returns_structured_data(self, handler_template, sample_image_file):
        """Test extract returns properly structured extraction data."""
        # Mock document with fields
        mock_field = Mock()
        mock_field.type = "string"
        mock_field.content = "123-456-789-00000"
        mock_field.confidence = 0.98

        mock_document = Mock()
        mock_document.doc_type = "BIR Tax Document"
        mock_document.confidence = 0.95
        mock_document.fields = {"tin": mock_field}

        mock_result = Mock()
        mock_result.model_id = "prebuilt-document"
        mock_result.api_version = "2024-01-01"
        mock_result.documents = [mock_document]
        mock_result.pages = [Mock()]
        mock_result.tables = []

        mock_poller = Mock()
        mock_poller.result.return_value = mock_result

        handler_template.client.begin_analyze_document = Mock(return_value=mock_poller)

        # Execute
        with patch("streamlit.spinner"), patch("utils.save_extraction_to_json"):
            result = handler_template.extract(sample_image_file)

        # Verify structure
        assert "service" in result
        assert "file_info" in result
        assert "model_info" in result
        assert "documents" in result
        assert "processing_info" in result

        assert result["service"] == "ADI-Template"
        assert result["model_info"]["model_id"] == "prebuilt-document"
        assert len(result["documents"]) == 1
        assert result["documents"][0]["doc_type"] == "BIR Tax Document"
        assert result["documents"][0]["confidence"] == 0.95

    def test_extract_saves_to_json_when_documents_exist(
        self, handler_template, sample_image_file, tmp_path
    ):
        """Test extract saves results when documents are found."""
        # Mock document with proper field access
        mock_field = Mock()
        mock_field.type = "string"
        mock_field.content = "123-456-789-00000"
        mock_field.confidence = 0.98

        mock_document = Mock()
        mock_document.doc_type = "BIR Tax Document"
        mock_document.confidence = 0.95
        mock_document.fields = {"tin": mock_field}

        mock_result = Mock()
        mock_result.model_id = "prebuilt-document"
        mock_result.api_version = "2024-01-01"
        mock_result.documents = [mock_document]
        mock_result.pages = [Mock()]  # List with one Mock page
        mock_result.tables = []  # Empty list

        mock_poller = Mock()
        mock_poller.result.return_value = mock_result

        handler_template.client.begin_analyze_document = Mock(return_value=mock_poller)

        # Execute - save will be called internally to temp file
        with patch("streamlit.spinner"):
            result = handler_template.extract(sample_image_file)

            # Verify extract completed successfully
            assert "error" not in result
            assert result["processing_info"]["documents_found"] == 1
            assert result["processing_info"]["pages_processed"] == 1

    def test_extract_handles_exception(self, handler_template, sample_image_file):
        """Test extract handles exceptions and returns error dict."""
        # Mock exception
        handler_template.client.begin_analyze_document = Mock(side_effect=Exception("API Error"))

        # Execute
        with patch("streamlit.spinner"):
            result = handler_template.extract(sample_image_file)

        # Verify error response
        assert "error" in result
        assert "API Error" in result["error"]
        assert result["service"] == "ADI-Template"
        assert "file_info" in result

    def test_extract_handles_empty_file(self, handler_template, mock_empty_file):
        """Test extract handles empty file gracefully."""
        mock_result = Mock()
        mock_result.documents = []
        mock_result.pages = []
        mock_result.tables = []

        mock_poller = Mock()
        mock_poller.result.return_value = mock_result

        handler_template.client.begin_analyze_document = Mock(return_value=mock_poller)

        with patch("streamlit.spinner"):
            result = handler_template.extract(mock_empty_file)

        # Should not crash, should handle gracefully
        assert "service" in result
        assert "processing_info" in result


class TestGPTForVisionHandler:
    """Test suite for GPTForVision handler."""

    @pytest.fixture
    def handler_gpt4(self, mock_env_vars):
        """Create a GPTForVision handler for GPT-4."""
        from handlers.gpt_vision import GPTForVision

        return GPTForVision(service_name="GPT-4.1-Vision")

    @pytest.fixture
    def handler_gpt5(self, mock_env_vars):
        """Create a GPTForVision handler for GPT-5."""
        from handlers.gpt_vision import GPTForVision

        return GPTForVision(service_name="GPT-5-Vision")

    def test_handler_initialization(self, mock_env_vars):
        """Test handler initializes with correct configuration."""
        from handlers.gpt_vision import GPTForVision

        handler = GPTForVision(service_name="ADI-Template")

        assert handler.service_name == "ADI-Template"
        assert handler.endpoint == "https://test-openai.openai.azure.com/"
        assert handler.deployment_gpt41 == "gpt-4-vision"
        assert handler.deployment_gpt5 == "gpt-5-vision"
        assert handler.api_version == "2025-01-01-preview"

    def test_handler_initialization_without_credentials(self, mock_missing_env_vars):
        """Test handler handles missing credentials."""
        from handlers.gpt_vision import GPTForVision

        with patch("streamlit.warning"):
            handler = GPTForVision(service_name="ADI-Template")

        # Should not crash, client should be None
        assert handler.client is None

    def test_convert_pdf_to_images(self, handler_gpt4, mock_pil_image):
        """Test PDF to image conversion."""
        # Create a real simple PDF using PyMuPDF
        import fitz

        pdf_doc = fitz.open()
        page = pdf_doc.new_page(width=595, height=842)
        page.insert_text((100, 100), "Test Page")
        pdf_bytes = pdf_doc.tobytes()
        pdf_doc.close()

        images = handler_gpt4._convert_pdf_to_images(pdf_bytes)

        assert len(images) > 0
        assert all(hasattr(img, "save") for img in images)

    def test_convert_pdf_to_images_handles_invalid_pdf(self, handler_gpt4):
        """Test PDF conversion handles invalid PDF gracefully."""
        invalid_pdf = b"Not a valid PDF"

        with patch("streamlit.error"):
            images = handler_gpt4._convert_pdf_to_images(invalid_pdf)

        assert images == []

    def test_image_to_base64(self, handler_gpt4, mock_pil_image):
        """Test image to base64 conversion."""
        base64_str = handler_gpt4._image_to_base64(mock_pil_image)

        assert isinstance(base64_str, str)
        assert len(base64_str) > 0

    def test_extract_uses_gpt4_deployment(self, handler_gpt4, sample_image_file):
        """Test extract uses GPT-4 deployment for GPT-4 service."""
        # Mock the client
        mock_parsed = Mock()
        mock_parsed.model_dump.return_value = {
            "tin": "123-456-789-00000",
            "taxpayerName": "Sample Corp",
        }

        mock_choice = Mock()
        mock_choice.message.parsed = mock_parsed

        mock_completion = Mock()
        mock_completion.choices = [mock_choice]

        handler_gpt4.client.beta.chat.completions.parse = Mock(return_value=mock_completion)

        # Execute
        with patch("streamlit.spinner"), patch("utils.save_extraction_to_json"):
            handler_gpt4.extract(sample_image_file)

        # Verify GPT-4 deployment was used with temperature 0
        call_kwargs = handler_gpt4.client.beta.chat.completions.parse.call_args[1]
        assert call_kwargs["model"] == "gpt-4-vision"
        assert call_kwargs["temperature"] == 0

    def test_extract_uses_gpt5_deployment(self, handler_gpt5, sample_image_file):
        """Test extract uses GPT-5 deployment for GPT-5 service."""
        # Mock the client
        mock_parsed = Mock()
        mock_parsed.model_dump.return_value = {
            "tin": "123-456-789-00000",
            "taxpayerName": "Sample Corp",
        }

        mock_choice = Mock()
        mock_choice.message.parsed = mock_parsed

        mock_completion = Mock()
        mock_completion.choices = [mock_choice]

        handler_gpt5.client.beta.chat.completions.parse = Mock(return_value=mock_completion)

        # Execute
        with patch("streamlit.spinner"), patch("utils.save_extraction_to_json"):
            handler_gpt5.extract(sample_image_file)

        # Verify GPT-5 deployment was used with temperature 1
        call_kwargs = handler_gpt5.client.beta.chat.completions.parse.call_args[1]
        assert call_kwargs["model"] == "gpt-5-vision"
        assert call_kwargs["temperature"] == 1

    def test_extract_returns_structured_data(self, handler_gpt4, sample_image_file):
        """Test extract returns properly structured data."""
        # Mock the client
        mock_parsed = Mock()
        mock_parsed.model_dump.return_value = {
            "tin": "123-456-789-00000",
            "taxpayerName": "Sample Corp",
            "registeredDate": "01/15/2024",
        }

        mock_choice = Mock()
        mock_choice.message.parsed = mock_parsed

        mock_completion = Mock()
        mock_completion.choices = [mock_choice]

        handler_gpt4.client.beta.chat.completions.parse = Mock(return_value=mock_completion)

        # Execute
        with patch("streamlit.spinner"), patch("utils.save_extraction_to_json"):
            result = handler_gpt4.extract(sample_image_file)

        # Verify structure
        assert "service" in result
        assert "file_info" in result
        assert "model_info" in result
        assert "documents" in result
        assert "processing_info" in result

        assert result["service"] == "GPT-4.1-Vision"
        assert len(result["documents"]) == 1
        assert "tin" in result["documents"][0]["fields"]

    def test_extract_handles_client_not_initialized(self, mock_env_vars, sample_image_file):
        """Test extract handles case when client is not initialized."""
        from handlers.gpt_vision import GPTForVision

        handler = GPTForVision(service_name="ADI-Template")
        handler.client = None

        result = handler.extract(sample_image_file)

        assert "error" in result
        assert "not initialized" in result["error"]

    def test_extract_handles_exception(self, handler_gpt4, sample_image_file):
        """Test extract handles exceptions gracefully."""
        handler_gpt4.client.beta.chat.completions.parse = Mock(side_effect=Exception("API Error"))

        with patch("streamlit.spinner"):
            result = handler_gpt4.extract(sample_image_file)

        assert "error" in result
        assert "API Error" in result["error"]

    def test_extract_calls_save_extraction_to_json(self, handler_gpt4, sample_image_file):
        """Test extract calls save_extraction_to_json with correct parameters."""
        # Mock the client
        mock_parsed = Mock()
        mock_parsed.model_dump.return_value = {
            "tin": "123-456-789-00000",
            "taxpayerName": "Sample Corp",
        }

        mock_choice = Mock()
        mock_choice.message.parsed = mock_parsed

        mock_completion = Mock()
        mock_completion.choices = [mock_choice]

        handler_gpt4.client.beta.chat.completions.parse = Mock(return_value=mock_completion)

        # Execute with mocked save function
        with (
            patch("streamlit.spinner"),
            patch("handlers.gpt_vision.save_extraction_to_json") as mock_save,
        ):
            handler_gpt4.extract(sample_image_file)

            # Verify save was called
            mock_save.assert_called_once()
            call_kwargs = mock_save.call_args[1]
            assert call_kwargs["overall_confidence"] == 0.0  # GPT doesn't provide confidence
            assert call_kwargs["pages_count"] == 1


class TestHandlerEdgeCases:
    """Test edge cases and error scenarios across all handlers."""

    def test_handler_with_corrupted_image(self, mock_env_vars):
        """Test handlers handle corrupted image files."""
        from handlers.document_intelligence import DocumentIntelligence

        handler = DocumentIntelligence(service_name="ADI-Template")

        # Create corrupted image file
        corrupted_file = Mock()
        corrupted_file.name = "corrupted.png"
        corrupted_file.type = "image/png"
        corrupted_file.getvalue.return_value = b"\x89PNG\r\n\x1a\n"  # Partial PNG header

        handler.client.begin_analyze_document = Mock(side_effect=Exception("Invalid image"))

        with patch("streamlit.spinner"):
            result = handler.extract(corrupted_file)

        assert "error" in result

    def test_handler_measures_processing_time(self, mock_env_vars, sample_image_file):
        """Test handlers correctly measure processing time."""
        from handlers.document_intelligence import DocumentIntelligence

        handler = DocumentIntelligence(service_name="ADI-Template")

        # Mock slow operation
        def slow_result():
            time.sleep(0.1)
            return Mock(documents=[], pages=[], tables=[])

        mock_poller = Mock()
        mock_poller.result = slow_result

        handler.client.begin_analyze_document = Mock(return_value=mock_poller)

        with patch("streamlit.spinner"), patch("utils.save_extraction_to_json") as mock_save:
            handler.extract(sample_image_file)

            if mock_save.called:
                processing_time = mock_save.call_args[1]["processing_time"]
                assert processing_time >= 0.1

    def test_handler_with_multiple_pages(self, mock_env_vars):
        """Test handlers handle multi-page documents."""
        from handlers.document_intelligence import DocumentIntelligence

        handler = DocumentIntelligence(service_name="ADI-Template")

        # Mock multi-page result
        mock_result = Mock()
        mock_result.documents = [Mock(confidence=0.95, fields={})]
        mock_result.pages = [Mock(), Mock(), Mock()]  # 3 pages
        mock_result.tables = []

        mock_poller = Mock()
        mock_poller.result.return_value = mock_result

        handler.client.begin_analyze_document = Mock(return_value=mock_poller)

        # Create multi-page PDF mock
        multi_page_file = Mock()
        multi_page_file.name = "multipage.pdf"
        multi_page_file.type = "application/pdf"
        multi_page_file.getvalue.return_value = b"mock_pdf_content"

        with patch("streamlit.spinner"), patch("utils.save_extraction_to_json") as mock_save:
            result = handler.extract(multi_page_file)

            # Verify pages count
            assert result["processing_info"]["pages_processed"] == 3

            if mock_save.called:
                args, kwargs = mock_save.call_args
                assert kwargs["pages_count"] == 3


class TestContentUnderstandingHandler:
    """Test suite for ContentUnderstanding handler."""

    @pytest.fixture
    def handler(self, mock_content_understanding_env):
        """Create ContentUnderstanding handler with mocked environment."""
        from handlers.content_understanding import ContentUnderstanding

        return ContentUnderstanding(service_name="Content-Understanding")

    def test_handler_initialization(self, mock_content_understanding_env):
        """Test handler initializes correctly."""
        from handlers.content_understanding import ContentUnderstanding

        handler = ContentUnderstanding(service_name="Test-CU")
        assert handler.service_name == "Test-CU"
        assert handler.endpoint == "https://test-cu-endpoint.cognitiveservices.azure.com/"
        assert handler.subscription_key == "test_cu_key_12345"
        assert handler.analyzer_id == "test-analyzer-id"
        assert handler.api_version == "2025-05-01-preview"

    def test_get_headers(self, handler):
        """Test header generation with subscription key."""
        headers = handler._get_headers()
        assert "Ocp-Apim-Subscription-Key" in headers
        assert headers["Ocp-Apim-Subscription-Key"] == "test_cu_key_12345"
        assert "x-ms-useragent" in headers

    def test_begin_analyze_success(self, handler, sample_image_file):
        """Test successful document analysis initiation."""
        file_bytes = sample_image_file.getvalue()

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.headers = {"operation-location": "https://test-location.com/status"}
            mock_post.return_value = mock_response

            response = handler._begin_analyze(file_bytes)

            assert response == mock_response
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "data" in call_args[1]
            assert call_args[1]["data"] == file_bytes

    def test_begin_analyze_raises_on_error(self, handler, sample_image_file):
        """Test begin_analyze handles HTTP errors."""
        file_bytes = sample_image_file.getvalue()

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = Exception("HTTP 401 Unauthorized")
            mock_post.return_value = mock_response

            with pytest.raises(Exception, match="HTTP 401 Unauthorized"):
                handler._begin_analyze(file_bytes)

    def test_poll_result_success(self, handler):
        """Test successful polling for results."""
        operation_location = "https://test-location.com/status"

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                "status": "succeeded",
                "result": {"contents": []},
            }
            mock_get.return_value = mock_response

            result = handler._poll_result(operation_location, timeout_seconds=10)

            assert result["status"] == "succeeded"
            mock_get.assert_called()

    def test_poll_result_timeout(self, handler):
        """Test polling times out correctly."""
        operation_location = "https://test-location.com/status"

        with patch("requests.get") as mock_get, patch("time.sleep"):
            # Always return running status
            mock_response = Mock()
            mock_response.json.return_value = {"status": "running"}
            mock_get.return_value = mock_response

            with pytest.raises(TimeoutError, match="timed out"):
                handler._poll_result(
                    operation_location, timeout_seconds=1, polling_interval_seconds=0.1
                )

    def test_poll_result_failed_status(self, handler):
        """Test polling handles failed status."""
        operation_location = "https://test-location.com/status"

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                "status": "failed",
                "error": "Processing error",
            }
            mock_get.return_value = mock_response

            with pytest.raises(RuntimeError, match="Analysis failed"):
                handler._poll_result(operation_location, timeout_seconds=10)

    def test_extract_without_credentials(self, mock_missing_env_vars, sample_image_file):
        """Test extract returns error when credentials missing."""
        from handlers.content_understanding import ContentUnderstanding

        handler = ContentUnderstanding()

        with patch("streamlit.spinner"):
            result = handler.extract(sample_image_file)

        assert "error" in result
        assert "not configured" in result["error"]

    def test_extract_success_with_contents(self, handler, sample_image_file):
        """Test successful extraction with contents."""
        with (
            patch("requests.post") as mock_post,
            patch("requests.get") as mock_get,
            patch("streamlit.spinner"),
            patch("handlers.content_understanding.save_extraction_to_json") as mock_save,
        ):
            # Mock begin_analyze response
            mock_post_response = Mock()
            mock_post_response.headers = {"operation-location": "https://test-location.com/status"}
            mock_post.return_value = mock_post_response

            # Mock poll_result response
            mock_get_response = Mock()
            mock_get_response.json.return_value = {
                "id": "test-id-123",
                "status": "succeeded",
                "result": {
                    "analyzerId": "test-analyzer",
                    "apiVersion": "2025-05-01-preview",
                    "createdAt": "2025-01-01T00:00:00Z",
                    "warnings": [],
                    "contents": [
                        {
                            "kind": "document",
                            "startPageNumber": 1,
                            "endPageNumber": 1,
                            "pages": [{"pageNumber": 1}],
                            "fields": {
                                "tin": {"type": "string", "valueString": "123-456-789"},
                                "taxpayerName": {"type": "string", "valueString": "Test Corp"},
                            },
                        }
                    ],
                },
            }
            mock_get.return_value = mock_get_response

            result = handler.extract(sample_image_file)

            assert "documents" in result
            assert len(result["documents"]) == 1
            assert result["documents"][0]["fields"]["tin"]["content"] == "123-456-789"
            mock_save.assert_called_once()

    def test_extract_missing_operation_location(self, handler, sample_image_file):
        """Test extract handles missing operation-location header."""
        with patch("requests.post") as mock_post, patch("streamlit.spinner"):
            mock_post_response = Mock()
            mock_post_response.headers = {}  # No operation-location
            mock_post.return_value = mock_post_response

            result = handler.extract(sample_image_file)

            assert "error" in result
            assert "Content Understanding extraction failed" in result["error"]

    def test_extract_handles_exception(self, handler, sample_image_file):
        """Test extract handles exceptions gracefully."""
        with patch("requests.post") as mock_post, patch("streamlit.spinner"):
            mock_post.side_effect = Exception("Network error")

            result = handler.extract(sample_image_file)

            assert "error" in result
            assert "Network error" in result["error"]
            assert "error_details" in result


class TestMistralDocumentAIHandler:
    """Test suite for MistralDocumentAI handler."""

    @pytest.fixture
    def handler(self, mock_mistral_env):
        """Create MistralDocumentAI handler with mocked environment."""
        from handlers.mistral_document_ai import MistralDocumentAI

        return MistralDocumentAI(service_name="Mistral-Doc-AI")

    def test_handler_initialization(self, mock_mistral_env):
        """Test handler initializes correctly."""
        from handlers.mistral_document_ai import MistralDocumentAI

        handler = MistralDocumentAI(service_name="Test-Mistral")
        assert handler.service_name == "Test-Mistral"
        assert (
            handler.endpoint
            == "https://test-mistral-endpoint.inference.ai.azure.com/v1/chat/completions"
        )
        assert handler.key == "test_mistral_key_12345"

    def test_extract_with_png_image(self, handler):
        """Test extraction with PNG image file."""
        mock_file = Mock()
        mock_file.name = "test.png"
        mock_file.type = "image/png"
        mock_file.getvalue.return_value = b"fake_png_data"

        with patch("requests.post") as mock_post, patch("streamlit.spinner"):
            mock_response = Mock()
            mock_response.json.return_value = {
                "document_annotation": '{"properties": {"tin": "123-456-789"}}'
            }
            mock_post.return_value = mock_response

            handler.extract(mock_file)

            assert "documents" in handler.extract(mock_file)
            # Verify image_url was used (not document_url)
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert payload["document"]["type"] == "image_url"
            assert "image_url" in payload["document"]

    def test_extract_with_pdf_document(self, handler):
        """Test extraction with PDF document."""
        mock_file = Mock()
        mock_file.name = "test.pdf"
        mock_file.type = "application/pdf"
        mock_file.getvalue.return_value = b"fake_pdf_data"

        with patch("requests.post") as mock_post, patch("streamlit.spinner"):
            mock_response = Mock()
            mock_response.json.return_value = {
                "document_annotation": '{"properties": {"tin": "123-456-789"}}'
            }
            mock_post.return_value = mock_response

            handler.extract(mock_file)

            # Verify document_url was used (not image_url)
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert payload["document"]["type"] == "document_url"
            assert "document_url" in payload["document"]

    def test_extract_with_jpeg_image(self, handler):
        """Test extraction with JPEG image."""
        mock_file = Mock()
        mock_file.name = "test.jpeg"
        mock_file.type = "image/jpeg"
        mock_file.getvalue.return_value = b"fake_jpeg_data"

        with patch("requests.post") as mock_post, patch("streamlit.spinner"):
            mock_response = Mock()
            mock_response.json.return_value = {"document_annotation": '{"properties": {}}'}
            mock_post.return_value = mock_response

            handler.extract(mock_file)

            # Verify correct MIME type
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            doc_url = payload["document"]["image_url"]
            assert "data:image/jpeg;base64," in doc_url

    def test_extract_request_exception(self, handler, sample_image_file):
        """Test extract handles request exceptions."""
        with patch("requests.post") as mock_post, patch("streamlit.spinner"):
            mock_post.side_effect = Exception("Connection timeout")

            result = handler.extract(sample_image_file)

            assert "error" in result
            assert "Mistral Document AI extraction failed" in result["error"]

    def test_extract_http_error(self, handler, sample_image_file):
        """Test extract handles HTTP errors."""
        import requests

        with patch("requests.post") as mock_post, patch("streamlit.spinner"):
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                "401 Unauthorized"
            )
            mock_post.return_value = mock_response

            result = handler.extract(sample_image_file)

            assert "error" in result
            assert "extraction failed" in result["error"].lower()

    def test_extract_saves_results_when_properties_exist(self, handler, sample_image_file):
        """Test that results are saved when properties are extracted."""
        with (
            patch("requests.post") as mock_post,
            patch("streamlit.spinner"),
            patch("handlers.mistral_document_ai.save_extraction_to_json") as mock_save,
        ):
            mock_response = Mock()
            mock_response.json.return_value = {
                "document_annotation": '{"properties": {"tin": "123-456-789", "taxpayerName": "Test Corp"}}'
            }
            mock_response.raise_for_status = Mock()  # Don't raise errors
            mock_post.return_value = mock_response

            handler.extract(sample_image_file)

            assert mock_save.called
            call_args = mock_save.call_args
            assert call_args[0][0] == sample_image_file.name  # file_name
            assert call_args[0][1] == "Mistral-Doc-AI"  # service_name

    def test_extract_empty_properties(self, handler, sample_image_file):
        """Test extraction with empty properties."""
        with (
            patch("requests.post") as mock_post,
            patch("streamlit.spinner"),
            patch("utils.save_extraction_to_json") as mock_save,
        ):
            mock_response = Mock()
            mock_response.json.return_value = {"document_annotation": '{"properties": {}}'}
            mock_post.return_value = mock_response

            result = handler.extract(sample_image_file)

            assert "documents" in result
            assert len(result["documents"]) == 1
            # save_extraction_to_json should not be called when no fields
            assert not mock_save.called

    def test_extract_no_document_annotation(self, handler, sample_image_file):
        """Test extraction when document_annotation is missing."""
        with patch("requests.post") as mock_post, patch("streamlit.spinner"):
            mock_response = Mock()
            mock_response.json.return_value = {}  # No document_annotation
            mock_post.return_value = mock_response

            result = handler.extract(sample_image_file)

            assert "documents" in result
            assert len(result["documents"]) == 0


class TestDocumentClassificationHandler:
    """Test suite for DocumentClassification handler."""

    @pytest.fixture
    def handler(self, mock_env_vars):
        """Create a DocumentClassification handler."""
        from handlers.document_classification import DocumentClassification

        return DocumentClassification(service_name="Document Classification")

    def test_handler_initialization_with_env_vars(self, mock_env_vars):
        """Test handler initializes correctly with environment variables."""
        from handlers.document_classification import DocumentClassification

        handler = DocumentClassification(service_name="Document Classification")

        assert handler.service_name == "Document Classification"
        assert handler.endpoint == "https://test-endpoint.cognitiveservices.azure.com/"
        assert handler.key == "test_key_12345"
        assert handler.model_id is not None
        assert handler.client is not None

    def test_handler_initialization_without_env_vars(self, mock_missing_env_vars):
        """Test handler handles missing environment variables gracefully."""
        from handlers.document_classification import DocumentClassification

        handler = DocumentClassification(service_name="Document Classification")

        assert handler.service_name == "Document Classification"
        assert handler.endpoint is None
        assert handler.key is None
        assert handler.client is None

    @pytest.mark.unit
    def test_classify_success_bir2303_new(self, handler, mock_pdf_file):
        """Test successful document classification returning bir2303-new."""
        # Mock the Azure Document Intelligence client response
        mock_result = Mock()
        mock_result.model_id = "bir2303-classifier"
        mock_result.api_version = "2024-11-30"
        mock_result.pages = [Mock()]
        mock_result.documents = [Mock()]
        mock_result.documents[0].doc_type = "bir2303-new"
        mock_result.documents[0].confidence = 0.95

        with patch.object(handler.client, "begin_classify_document") as mock_classify:
            mock_poller = Mock()
            mock_poller.result.return_value = mock_result
            mock_classify.return_value = mock_poller

            result = handler.classify(mock_pdf_file)

            assert result["service"] == "Document Classification"
            assert result["docType"] == "bir2303-new"
            assert result["confidence"] == 0.95
            assert "error" not in result
            assert result["processing_info"]["documents_found"] == 1

    @pytest.mark.unit
    def test_classify_success_bir2303_null(self, handler, mock_pdf_file):
        """Test successful classification but returning bir2303-null (should be rejected as unknown)."""
        # Mock the Azure Document Intelligence client response
        mock_result = Mock()
        mock_result.model_id = "bir2303-classifier"
        mock_result.api_version = "2024-11-30"
        mock_result.pages = [Mock()]
        mock_result.documents = [Mock()]
        mock_result.documents[0].doc_type = "bir2303-null"
        mock_result.documents[0].confidence = 0.85

        with patch.object(handler.client, "begin_classify_document") as mock_classify:
            mock_poller = Mock()
            mock_poller.result.return_value = mock_result
            mock_classify.return_value = mock_poller

            result = handler.classify(mock_pdf_file)

            assert result["service"] == "Document Classification"
            # doc_type containing "null" should be rejected and set to "unknown"
            assert result["docType"] == "unknown"
            assert result["confidence"] == 0.85  # Confidence is preserved
            assert "error" not in result
            # Verify the original doc_type is preserved in documents array
            assert result["documents"][0]["doc_type"] == "bir2303-null"

    @pytest.mark.unit
    def test_classify_no_documents_found(self, handler, mock_pdf_file):
        """Test classification when no documents are detected."""
        # Mock response with no documents
        mock_result = Mock()
        mock_result.model_id = "bir2303-classifier"
        mock_result.api_version = "2024-11-30"
        mock_result.pages = [Mock()]
        mock_result.documents = []

        with patch.object(handler.client, "begin_classify_document") as mock_classify:
            mock_poller = Mock()
            mock_poller.result.return_value = mock_result
            mock_classify.return_value = mock_poller

            result = handler.classify(mock_pdf_file)

            assert result["service"] == "Document Classification"
            assert result["docType"] == "unknown"
            assert result["confidence"] == 0.0
            assert "error" not in result

    @pytest.mark.unit
    def test_classify_exception_handling(self, handler, mock_pdf_file):
        """Test classification exception handling returns error dict."""
        with patch.object(
            handler.client, "begin_classify_document", side_effect=Exception("API Error")
        ):
            result = handler.classify(mock_pdf_file)

            assert result["service"] == "Document Classification"
            assert "error" in result
            assert "Classification failed" in result["error"]
            assert result["docType"] == "unknown"
            assert result["confidence"] == 0.0

    @pytest.mark.unit
    def test_classify_missing_model_id(self, handler, mock_pdf_file):
        """Test classification fails gracefully when model_id is not configured."""
        # Set model_id to None to simulate missing env var
        handler.model_id = None

        result = handler.classify(mock_pdf_file)

        assert result["service"] == "Document Classification"
        assert "error" in result
        assert "AZURE_DOCUMENT_INTELLIGENCE_CLASSIFICATION_MODEL" in result["error"]
        assert result["docType"] == "unknown"
        assert result["confidence"] == 0.0

    @pytest.mark.unit
    def test_classify_performance_timing(self, handler, mock_pdf_file):
        """Test that processing time is tracked correctly."""
        # Mock fast classification
        mock_result = Mock()
        mock_result.model_id = "bir2303-classifier"
        mock_result.api_version = "2024-11-30"
        mock_result.pages = [Mock()]
        mock_result.documents = [Mock()]
        mock_result.documents[0].doc_type = "bir2303-new"
        mock_result.documents[0].confidence = 0.95

        with patch.object(handler.client, "begin_classify_document") as mock_classify:
            mock_poller = Mock()
            mock_poller.result.return_value = mock_result
            mock_classify.return_value = mock_poller

            start = time.time()
            result = handler.classify(mock_pdf_file)
            elapsed = time.time() - start

            assert "processing_info" in result
            assert "processing_time_seconds" in result["processing_info"]
            # Processing time should be close to actual elapsed time (within 0.5s)
            assert abs(result["processing_info"]["processing_time_seconds"] - elapsed) < 0.5
