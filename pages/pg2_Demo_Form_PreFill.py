"""Demo Form Pre-Fill page for document extraction.

This page allows users to upload a document, select an extraction service,
and automatically pre-fill a form with extracted data.
"""

import asyncio
import concurrent.futures
import io
import logging
import sys
import time
from typing import Any

import fitz  # PyMuPDF
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

sys.path.append("..")
from handlers.content_understanding import ContentUnderstanding
from handlers.document_intelligence import DocumentIntelligence
from handlers.gpt_vision import GPTForVision
from handlers.mistral_document_ai import MistralDocumentAI
from utils import render_sidebar

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


# Service configuration mapping
SERVICE_CONFIG = {
    "Document Intelligence - Template": ("ADI-Template", DocumentIntelligence),
    "Document Intelligence - Neural": ("ADI-Neural", DocumentIntelligence),
    "Content Understanding": ("Content-Understanding", ContentUnderstanding),
    "Mistral Document AI": ("Mistral-Doc-AI", MistralDocumentAI),
    "GPT-4.1 for Vision": ("GPT-4.1-Vision", GPTForVision),
    "GPT-5 for Vision": ("GPT-5-Vision", GPTForVision),
}


def is_valid_file_type(file):
    """Check if uploaded file has a valid type for document extraction."""
    allowed_types = ["pdf", "png", "jpg", "jpeg"]
    if file is not None and hasattr(file, "name"):
        file_extension = file.name.lower().split(".")[-1]
        return file_extension in allowed_types
    return False


def render_pdf_page_as_image(pdf_bytes: bytes, page_num: int = 0, zoom: float = 2.0) -> Image:
    """
    Render a specific page of a PDF as a PIL Image.

    Args:
        pdf_bytes: PDF file content as bytes
        page_num: Page number to render (0-indexed)
        zoom: Zoom factor for rendering quality (default: 2.0 for high quality)

    Returns:
        PIL Image of the rendered page
    """
    # Open PDF from bytes
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Get the specified page
    page = doc[page_num]

    # Create transformation matrix for rendering
    mat = fitz.Matrix(zoom, zoom)

    # Render page to pixmap
    pix = page.get_pixmap(matrix=mat)

    # Convert pixmap to PIL Image
    img_data = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_data))

    doc.close()

    return img


async def extract_with_service_async(svc_name: str, svc_class, file) -> dict[str, Any]:
    """
    Asynchronously extract data using a specific service.

    Args:
        svc_name: Name of the service
        svc_class: Service class to instantiate
        file: File to process

    Returns:
        Dictionary containing extraction results
    """
    start_time = time.time()

    try:
        # Run the potentially blocking extraction in a thread pool
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Create service instance and run extraction in executor
            svc = svc_class(svc_name)
            # Suppress logging temporarily while running in executor
            old_level = logging.getLogger("streamlit").level
            logging.getLogger("streamlit").setLevel(logging.ERROR)
            try:
                result = await loop.run_in_executor(executor, svc.extract, file)
            finally:
                logging.getLogger("streamlit").setLevel(old_level)

        processing_time = time.time() - start_time
        logger.info(f"Extraction completed: {svc_name} | {file.name} | {processing_time:.3f}s")

        return result

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Extraction failed: {svc_name} | {file.name} | {str(e)}", exc_info=True)
        return {
            "service": svc_name,
            "error": f"Extraction failed: {str(e)}",
            "processing_time": processing_time,
        }


def extract_field_value(extraction_result: dict[str, Any], field_name: str) -> str:
    """
    Extract a specific field value from extraction results.

    Args:
        extraction_result: The extraction result dictionary
        field_name: Name of the field to extract

    Returns:
        Field value as string, or empty string if not found
    """
    try:
        # Handle error cases
        if "error" in extraction_result:
            return ""

        # Check if documents exist in result
        documents = extraction_result.get("documents", [])
        if not documents:
            return ""

        # Get first document's fields
        first_doc = documents[0]
        fields = first_doc.get("fields", {})

        # Extract the specific field
        if field_name in fields:
            field_data = fields[field_name]
            # Try to get content, then value, then fallback to empty
            return str(field_data.get("content", field_data.get("value", "")))

        return ""

    except Exception as e:
        logger.error(f"Field extraction error: {field_name} | {str(e)}")
        return ""


def initialize_session_state():
    """Initialize session state variables for the form pre-fill page."""
    if "prefill_uploaded_file" not in st.session_state:
        st.session_state.prefill_uploaded_file = None

    if "prefill_selected_service" not in st.session_state:
        st.session_state.prefill_selected_service = None

    if "prefill_selected_service_display" not in st.session_state:
        st.session_state.prefill_selected_service_display = "-- Select a service --"

    if "prefill_extraction_result" not in st.session_state:
        st.session_state.prefill_extraction_result = None

    if "prefill_form_data" not in st.session_state:
        st.session_state.prefill_form_data = {
            "tin": "",
            "taxpayerName": "",
            "registeredDate": "",
            "registeredAddress": "",
            "tradeName": "",
            "businessType": "",
        }


def main():
    logger.info("Demo Form Pre-Fill page loaded")
    render_sidebar()

    st.header("📝 Demo Form Pre-Fill")
    st.markdown(
        """
        Upload a document and select an extraction service to automatically pre-fill the form below.
        """
    )

    # Initialize session state
    initialize_session_state()

    # Section 1 & 2: Upload Document and Select Extraction Service
    with st.container(border=True):
        col_upload, col_service = st.columns(2, gap="medium")

        # LEFT COLUMN: Upload Document
        with col_upload:
            st.subheader("1️⃣ Upload Document")
            uploaded_file = st.file_uploader(
                "Choose a file (PDF or image)",
                type=["pdf", "png", "jpg", "jpeg"],
                key="prefill_file_uploader",
            )

            # Validate and store uploaded file
            if uploaded_file:
                if is_valid_file_type(uploaded_file):
                    st.session_state.prefill_uploaded_file = uploaded_file
                    st.success(f"✅ **{uploaded_file.name}** uploaded successfully!")
                else:
                    st.error(
                        "❌ Invalid file type. Please upload PDF, PNG, JPG, or JPEG files only."
                    )
                    st.session_state.prefill_uploaded_file = None
            elif st.session_state.prefill_uploaded_file:
                # Show previously uploaded file
                st.info(
                    f"📁 Using previously uploaded file: **{st.session_state.prefill_uploaded_file.name}**"
                )

        # RIGHT COLUMN: Select Extraction Service
        with col_service:
            st.subheader("2️⃣ Select Extraction Service")

            selected_service_display = st.selectbox(
                "Choose an extraction service",
                options=["-- Select a service --"] + list(SERVICE_CONFIG.keys()),
                index=(["-- Select a service --"] + list(SERVICE_CONFIG.keys())).index(
                    st.session_state.prefill_selected_service_display
                )
                if st.session_state.prefill_selected_service_display
                in ["-- Select a service --"] + list(SERVICE_CONFIG.keys())
                else 0,
                key="prefill_service_selector",
            )

            if selected_service_display != "-- Select a service --":
                st.session_state.prefill_selected_service = selected_service_display
                st.session_state.prefill_selected_service_display = selected_service_display
                st.success(f"✅ Selected: **{selected_service_display}**")
            else:
                st.session_state.prefill_selected_service = None
                st.session_state.prefill_selected_service_display = "-- Select a service --"

    # Section 3: Pre-Fill Button (appears when file and service are selected)
    has_valid_file = st.session_state.prefill_uploaded_file is not None
    has_valid_service = (
        st.session_state.prefill_selected_service is not None
        and st.session_state.prefill_selected_service in SERVICE_CONFIG
    )

    if has_valid_file and has_valid_service:
        # Pre-Fill Form Section
        st.markdown("### 3️⃣ Pre-Fill Form")

        col_button, col_clear = st.columns([3, 1])

        with col_button:
            if st.button("🚀 Pre-Fill Form", type="primary", width="stretch"):
                # Get service configuration
                service_name, service_class = SERVICE_CONFIG[
                    st.session_state.prefill_selected_service
                ]

                with st.spinner(
                    f"Extracting data using {st.session_state.prefill_selected_service}..."
                ):
                    try:
                        # Run extraction asynchronously
                        extraction_result = asyncio.run(
                            extract_with_service_async(
                                service_name, service_class, st.session_state.prefill_uploaded_file
                            )
                        )

                        # Store extraction result
                        st.session_state.prefill_extraction_result = extraction_result

                        # Check for errors
                        if "error" in extraction_result:
                            st.error(
                                f"❌ Extraction failed: {extraction_result.get('error', 'Unknown error')}"
                            )
                        else:
                            # Extract field values and populate form data
                            st.session_state.prefill_form_data["tin"] = extract_field_value(
                                extraction_result, "tin"
                            )
                            st.session_state.prefill_form_data["taxpayerName"] = (
                                extract_field_value(extraction_result, "taxpayerName")
                            )
                            st.session_state.prefill_form_data["registeredDate"] = (
                                extract_field_value(extraction_result, "registeredDate")
                            )
                            st.session_state.prefill_form_data["registeredAddress"] = (
                                extract_field_value(extraction_result, "registeredAddress")
                            )
                            st.session_state.prefill_form_data["tradeName"] = extract_field_value(
                                extraction_result, "tradeName"
                            )
                            st.session_state.prefill_form_data["businessType"] = (
                                extract_field_value(extraction_result, "businessType")
                            )

                            st.success("✅ Form pre-filled successfully!")
                            st.rerun()

                    except Exception as e:
                        logger.error(f"Pre-fill extraction error: {str(e)}", exc_info=True)
                        st.error(f"❌ Extraction failed: {str(e)}")

        with col_clear:
            if st.button("🗑️ Clear", width="stretch"):
                # Reset session state
                st.session_state.prefill_uploaded_file = None
                st.session_state.prefill_selected_service = None
                st.session_state.prefill_selected_service_display = "-- Select a service --"
                st.session_state.prefill_extraction_result = None
                st.session_state.prefill_form_data = {
                    "tin": "",
                    "taxpayerName": "",
                    "registeredDate": "",
                    "registeredAddress": "",
                    "tradeName": "",
                    "businessType": "",
                }
                st.rerun()

    # Section 4: Display Form (always visible, pre-filled after extraction)
    st.markdown("---")
    st.subheader("📋 Document Information Form")

    # Show extraction info if available
    if (
        st.session_state.prefill_extraction_result
        and "error" not in st.session_state.prefill_extraction_result
    ):
        processing_info = st.session_state.prefill_extraction_result.get("processing_info", {})
        if processing_info:
            st.caption(
                f"🔍 Extracted from **{st.session_state.prefill_uploaded_file.name}** "
                f"using **{st.session_state.prefill_selected_service}** "
                f"in {processing_info.get('processing_time_seconds', 0):.3f}s"
            )

    # Create form with two-column layout: fields on left, preview on right
    col_form, col_preview = st.columns([1.2, 1], gap="medium")

    # LEFT COLUMN: Form fields
    with col_form, st.container(border=True):
        st.markdown("**BIR Tax Document Information**")

        st.text_input(
            "TIN Number",
            value=st.session_state.prefill_form_data.get("tin", ""),
            placeholder="XXX-XXX-XXX-XXXXX",
            help="Taxpayer Identification Number",
        )

        st.text_input(
            "Taxpayer Name",
            value=st.session_state.prefill_form_data.get("taxpayerName", ""),
            placeholder="Enter taxpayer name",
            help="Full name of the taxpayer or business entity",
        )

        st.text_input(
            "Registered Date",
            value=st.session_state.prefill_form_data.get("registeredDate", ""),
            placeholder="MM/DD/YYYY",
            help="Date the TIN was issued or registered",
        )

        st.text_input(
            "Trade Name",
            value=st.session_state.prefill_form_data.get("tradeName", ""),
            placeholder="Enter trade name",
            help="Registered trade name or business name",
        )

        st.text_input(
            "Business Type",
            value=st.session_state.prefill_form_data.get("businessType", ""),
            placeholder="Enter business type",
            help="Line of business or business activities",
        )

        st.text_area(
            "Registered Address",
            value=st.session_state.prefill_form_data.get("registeredAddress", ""),
            placeholder="Enter complete registered address",
            help="Complete registered address of the taxpayer or business",
        )

    # RIGHT COLUMN: File preview
    with col_preview:
        if st.session_state.prefill_uploaded_file:
            with st.container(border=True):
                st.markdown("**📄 Document Preview**")

                file_name = st.session_state.prefill_uploaded_file.name
                file_extension = file_name.lower().split(".")[-1]

                try:
                    if file_extension == "pdf":
                        # For PDF files, render all pages in tabs
                        pdf_bytes = st.session_state.prefill_uploaded_file.getvalue()
                        file_size_mb = len(pdf_bytes) / (1024 * 1024)

                        # Open PDF to get page count
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        page_count = len(doc)
                        doc.close()

                        st.caption(
                            f"📑 **PDF Document** | Pages: {page_count} | Size: {file_size_mb:.2f} MB"
                        )

                        # Create tabs for each page
                        if page_count > 0:
                            tab_labels = [f"Page {i + 1}" for i in range(page_count)]
                            tabs = st.tabs(tab_labels)

                            for page_num, tab in enumerate(tabs):
                                with tab:
                                    preview_img = render_pdf_page_as_image(
                                        pdf_bytes, page_num=page_num, zoom=1.5
                                    )
                                    st.image(preview_img)
                        else:
                            st.warning("PDF document is empty or corrupted.")

                    elif file_extension in ["png", "jpg", "jpeg"]:
                        # For image files, display the image
                        st.image(
                            st.session_state.prefill_uploaded_file,
                            caption=f"Image: {file_name}",
                        )

                except Exception as e:
                    st.warning(f"⚠️ Could not display preview: {str(e)}")
        else:
            with st.container(border=True):
                st.markdown("**📄 Document Preview**")
                st.info("📁 No file uploaded yet. Upload a document to see preview here.")

    # Help section
    st.markdown("---")
    st.markdown("### 💡 How to Use")

    col_help1, col_help2 = st.columns(2)

    with col_help1:
        st.info(
            """
        **Step-by-Step Guide:**
        1. Upload a BIR tax document (PDF or image)
        2. Select an extraction service from the dropdown
        3. Click "Pre-Fill Form" to extract data
        4. Review and edit the pre-filled form
        5. Click "Submit Form" to complete
        """
        )

    with col_help2:
        st.info(
            """
        **Supported Services:**
        - Document Intelligence (Template/Neural)
        - Content Understanding
        - Mistral Document AI
        - GPT-4.1 for Vision
        - GPT-5 for Vision
        """
        )


if __name__ == "__main__":
    main()
