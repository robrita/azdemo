"""
Unit tests for utils.py module.

Tests the utility functions including save_extraction_to_json,
keep_state, and render_sidebar.
"""

import json
from unittest.mock import mock_open, patch


class TestSaveExtractionToJson:
    """Test suite for save_extraction_to_json function."""

    def test_save_extraction_creates_new_file(self, temp_output_dir):
        """Test saving extraction results creates new JSON file when none exists."""
        from utils import save_extraction_to_json

        results_file = temp_output_dir / "test_results.json"

        fields = {
            "tin": {"content": "123-456-789-00000", "confidence": 0.98},
            "taxpayerName": {"content": "Sample Corp", "confidence": 0.96},
        }

        save_extraction_to_json(
            file_name="test_file.png",
            service_name="Test Service",
            pages_count=1,
            fields=fields,
            overall_confidence=0.95,
            processing_time=2.5,
            results_file_path=str(results_file),
        )

        # Verify file was created
        assert results_file.exists()

        # Verify content structure
        with open(results_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["file_name"] == "test_file.png"
        assert data["results"][0]["service_name"] == "Test Service"
        assert data["results"][0]["pages_count"] == 1
        assert data["results"][0]["document_confidence"] == 0.95
        assert data["results"][0]["processing_time"] == 2.5

    def test_save_extraction_appends_to_existing_file(self, temp_output_dir):
        """Test saving extraction appends to existing results file."""
        from utils import save_extraction_to_json

        results_file = temp_output_dir / "test_results.json"

        # Create initial file with one result
        initial_data = {
            "results": [
                {
                    "file_name": "existing_file.png",
                    "service_name": "Existing Service",
                    "pages_count": 1,
                    "document_confidence": 0.90,
                    "processing_time": 1.5,
                    "fields": [],
                }
            ]
        }

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(initial_data, f)

        # Add new result
        fields = {"tin": {"content": "123-456-789-00000", "confidence": 0.98}}

        save_extraction_to_json(
            file_name="new_file.png",
            service_name="New Service",
            pages_count=1,
            fields=fields,
            overall_confidence=0.95,
            processing_time=2.5,
            results_file_path=str(results_file),
        )

        # Verify both results exist
        with open(results_file, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["results"]) == 2
        assert data["results"][0]["file_name"] == "existing_file.png"
        assert data["results"][1]["file_name"] == "new_file.png"

    def test_save_extraction_updates_existing_entry(self, temp_output_dir):
        """Test saving extraction updates existing entry with same file_name and service_name."""
        from utils import save_extraction_to_json

        results_file = temp_output_dir / "test_results.json"

        # Create initial file
        initial_data = {
            "results": [
                {
                    "file_name": "test_file.png",
                    "service_name": "Test Service",
                    "pages_count": 1,
                    "document_confidence": 0.80,
                    "processing_time": 1.0,
                    "fields": [],
                }
            ]
        }

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(initial_data, f)

        # Update with new data
        fields = {"tin": {"content": "123-456-789-00000", "confidence": 0.98}}

        save_extraction_to_json(
            file_name="test_file.png",
            service_name="Test Service",
            pages_count=1,
            fields=fields,
            overall_confidence=0.95,
            processing_time=2.5,
            results_file_path=str(results_file),
        )

        # Verify entry was updated, not duplicated
        with open(results_file, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["results"]) == 1
        assert data["results"][0]["document_confidence"] == 0.95
        assert data["results"][0]["processing_time"] == 2.5

    def test_save_extraction_rounds_confidence_to_three_decimals(self, temp_output_dir):
        """Test confidence scores are rounded to 3 decimal places."""
        from utils import save_extraction_to_json

        results_file = temp_output_dir / "test_results.json"

        fields = {
            "tin": {"content": "123-456-789-00000", "confidence": 0.987654321},
            "taxpayerName": {"content": "Sample Corp", "confidence": 0.123456789},
        }

        save_extraction_to_json(
            file_name="test_file.png",
            service_name="Test Service",
            pages_count=1,
            fields=fields,
            overall_confidence=0.956789,
            processing_time=2.567891,
            results_file_path=str(results_file),
        )

        with open(results_file, encoding="utf-8") as f:
            data = json.load(f)

        # Check overall confidence rounded
        assert data["results"][0]["document_confidence"] == 0.957

        # Check processing time rounded
        assert data["results"][0]["processing_time"] == 2.568

        # Check field confidences rounded
        field_confidences = {
            field["name"]: field["confidence"] for field in data["results"][0]["fields"]
        }
        assert field_confidences["tin"] == 0.988
        assert field_confidences["taxpayerName"] == 0.123

    def test_save_extraction_with_none_confidence_defaults_to_zero(self, temp_output_dir):
        """Test None confidence values default to 0.0."""
        from utils import save_extraction_to_json

        results_file = temp_output_dir / "test_results.json"

        fields = {"tin": {"content": "123-456-789-00000", "confidence": 0.98}}

        save_extraction_to_json(
            file_name="test_file.png",
            service_name="Test Service",
            pages_count=1,
            fields=fields,
            overall_confidence=None,
            processing_time=None,
            results_file_path=str(results_file),
        )

        with open(results_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["results"][0]["document_confidence"] == 0.0
        assert data["results"][0]["processing_time"] == 0.0

    def test_save_extraction_handles_fields_with_value_key(self, temp_output_dir):
        """Test extraction handles fields using 'value' instead of 'content'."""
        from utils import save_extraction_to_json

        results_file = temp_output_dir / "test_results.json"

        # Use 'value' key instead of 'content'
        fields = {
            "tin": {"value": "123-456-789-00000", "confidence": 0.98},
            "taxpayerName": {"value": "Sample Corp", "confidence": 0.96},
        }

        save_extraction_to_json(
            file_name="test_file.png",
            service_name="Test Service",
            pages_count=1,
            fields=fields,
            overall_confidence=0.95,
            processing_time=2.5,
            results_file_path=str(results_file),
        )

        with open(results_file, encoding="utf-8") as f:
            data = json.load(f)

        # Verify values were extracted correctly
        field_values = {field["name"]: field["value"] for field in data["results"][0]["fields"]}
        assert field_values["tin"] == "123-456-789-00000"
        assert field_values["taxpayerName"] == "Sample Corp"

    def test_save_extraction_handles_missing_confidence_in_fields(self, temp_output_dir):
        """Test extraction handles fields without confidence key."""
        from utils import save_extraction_to_json

        results_file = temp_output_dir / "test_results.json"

        # Fields without confidence
        fields = {
            "tin": {"content": "123-456-789-00000"},
            "taxpayerName": {"content": "Sample Corp"},
        }

        save_extraction_to_json(
            file_name="test_file.png",
            service_name="Test Service",
            pages_count=1,
            fields=fields,
            overall_confidence=0.95,
            processing_time=2.5,
            results_file_path=str(results_file),
        )

        with open(results_file, encoding="utf-8") as f:
            data = json.load(f)

        # Verify confidence defaults to 0.0
        for field in data["results"][0]["fields"]:
            assert field["confidence"] == 0.0

    def test_save_extraction_creates_directory_if_not_exists(self, tmp_path):
        """Test extraction creates output directory if it doesn't exist."""
        from utils import save_extraction_to_json

        results_file = tmp_path / "non_existent_dir" / "results.json"

        fields = {"tin": {"content": "123-456-789-00000", "confidence": 0.98}}

        save_extraction_to_json(
            file_name="test_file.png",
            service_name="Test Service",
            pages_count=1,
            fields=fields,
            overall_confidence=0.95,
            processing_time=2.5,
            results_file_path=str(results_file),
        )

        # Verify directory and file were created
        assert results_file.parent.exists()
        assert results_file.exists()

    @patch("streamlit.warning")
    def test_save_extraction_handles_json_write_error(self, mock_warning, tmp_path):
        """Test extraction handles errors when writing JSON file."""
        from utils import save_extraction_to_json

        # Create a read-only directory (Windows compatible)
        results_file = tmp_path / "readonly" / "results.json"
        results_file.parent.mkdir()

        fields = {"tin": {"content": "123-456-789-00000", "confidence": 0.98}}

        # Mock the open function to raise an exception
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            save_extraction_to_json(
                file_name="test_file.png",
                service_name="Test Service",
                pages_count=1,
                fields=fields,
                overall_confidence=0.95,
                processing_time=2.5,
                results_file_path=str(results_file),
            )

        # Verify warning was called
        mock_warning.assert_called_once()
        assert "Failed to save results to JSON" in mock_warning.call_args[0][0]


class TestKeepState:
    """Test suite for keep_state function."""

    @patch("streamlit.session_state", new_callable=dict)
    def test_keep_state_stores_value(self, mock_session_state):
        """Test keep_state stores value in session state."""
        from utils import keep_state

        result = keep_state("test_value", "test_key")

        assert mock_session_state["test_key"] == "test_value"
        assert result is False

    @patch("streamlit.session_state", new_callable=dict)
    def test_keep_state_returns_true_when_key_exists(self, mock_session_state):
        """Test keep_state returns True when key already exists."""
        from utils import keep_state

        # Pre-populate session state
        mock_session_state["existing_key"] = "existing_value"

        result = keep_state(None, "existing_key")

        assert result is True
        assert mock_session_state["existing_key"] == "existing_value"

    @patch("streamlit.session_state", new_callable=dict)
    def test_keep_state_updates_existing_value(self, mock_session_state):
        """Test keep_state updates existing value when new value provided."""
        from utils import keep_state

        # Pre-populate session state
        mock_session_state["test_key"] = "old_value"

        result = keep_state("new_value", "test_key")

        assert mock_session_state["test_key"] == "new_value"
        assert result is False

    @patch("streamlit.session_state", new_callable=dict)
    def test_keep_state_handles_empty_string(self, mock_session_state):
        """Test keep_state treats empty string as falsy."""
        from utils import keep_state

        result = keep_state("", "test_key")

        assert "test_key" not in mock_session_state
        assert result is False

    @patch("streamlit.session_state", new_callable=dict)
    def test_keep_state_handles_zero(self, mock_session_state):
        """Test keep_state treats zero as falsy."""
        from utils import keep_state

        result = keep_state(0, "test_key")

        assert "test_key" not in mock_session_state
        assert result is False

    @patch("streamlit.session_state", new_callable=dict)
    def test_keep_state_handles_list(self, mock_session_state):
        """Test keep_state stores list values."""
        from utils import keep_state

        test_list = [1, 2, 3, 4, 5]
        result = keep_state(test_list, "list_key")

        assert mock_session_state["list_key"] == test_list
        assert result is False

    @patch("streamlit.session_state", new_callable=dict)
    def test_keep_state_handles_dict(self, mock_session_state):
        """Test keep_state stores dictionary values."""
        from utils import keep_state

        test_dict = {"key1": "value1", "key2": "value2"}
        result = keep_state(test_dict, "dict_key")

        assert mock_session_state["dict_key"] == test_dict
        assert result is False


class TestRenderSidebar:
    """Test suite for render_sidebar function."""

    @patch("streamlit.set_page_config")
    @patch("streamlit.logo")
    @patch("builtins.open", mock_open(read_data="body { color: red; }"))
    @patch("streamlit.markdown")
    @patch("streamlit.sidebar")
    def test_render_sidebar_configures_page(
        self, mock_sidebar, mock_markdown, mock_logo, mock_config
    ):
        """Test render_sidebar sets up page configuration."""
        from utils import render_sidebar

        render_sidebar()

        # Verify page config was called
        mock_config.assert_called_once_with(
            page_title="Document Processing Dashboard",
            page_icon="🚀",
            layout="wide",
            initial_sidebar_state="expanded",
        )

    @patch("streamlit.set_page_config")
    @patch("streamlit.logo")
    @patch("builtins.open", mock_open(read_data="body { color: red; }"))
    @patch("streamlit.markdown")
    @patch("streamlit.sidebar")
    def test_render_sidebar_loads_css(
        self, mock_sidebar, mock_markdown, mock_logo, mock_config
    ):
        """Test render_sidebar loads CSS file."""
        from utils import render_sidebar

        render_sidebar()

        # Verify markdown was called with CSS
        assert mock_markdown.called
        call_args = mock_markdown.call_args[0][0]
        assert "<style>" in call_args
        assert "body { color: red; }" in call_args

    @patch("streamlit.set_page_config")
    @patch("streamlit.logo")
    @patch("builtins.open", mock_open(read_data=""))
    @patch("streamlit.markdown")
    @patch("streamlit.sidebar")
    def test_render_sidebar_sets_logo(
        self, mock_sidebar, mock_markdown, mock_logo, mock_config
    ):
        """Test render_sidebar sets Azure AI logo."""
        from utils import render_sidebar

        render_sidebar()

        # Verify logo was called
        mock_logo.assert_called_once()
        assert "ai-foundry.png" in mock_logo.call_args[0][0]
        assert mock_logo.call_args[1]["link"] == "https://ai.azure.com/"
