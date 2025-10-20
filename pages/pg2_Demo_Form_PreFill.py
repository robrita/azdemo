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
from handlers.document_classification import DocumentClassification
from handlers.document_intelligence import DocumentIntelligence
from handlers.gpt_vision import GPTForVision
from handlers.mistral_document_ai import MistralDocumentAI
from utils import render_sidebar

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Default service for form pre-fill
DEFAULT_SERVICE = "Document Intelligence - Template"

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

        # Extract processing time from handler's result (if available in processing_info)
        if "processing_info" in result and "processing_time_seconds" in result["processing_info"]:
            result["processing_time"] = result["processing_info"]["processing_time_seconds"]
        else:
            # Fallback: use our measured time if handler doesn't provide it
            result["processing_time"] = processing_time

        return result

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Extraction failed: {svc_name} | {file.name} | {str(e)}", exc_info=True)
        return {
            "service": svc_name,
            "error": f"Extraction failed: {str(e)}",
            "processing_time": processing_time,
        }


async def classify_document_async(file) -> dict[str, Any]:
    """
    Asynchronously classify document type before extraction.

    Args:
        file: File to classify

    Returns:
        Dictionary containing classification results with docType and confidence
    """
    start_time = time.time()

    try:
        # Run the potentially blocking classification in a thread pool
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Create classification service instance
            classifier = DocumentClassification()
            # Suppress logging temporarily while running in executor
            old_level = logging.getLogger("streamlit").level
            logging.getLogger("streamlit").setLevel(logging.ERROR)
            try:
                result = await loop.run_in_executor(executor, classifier.classify, file)
            finally:
                logging.getLogger("streamlit").setLevel(old_level)

        processing_time = time.time() - start_time
        logger.info(
            f"Classification completed: {file.name} | "
            f"Type: {result.get('docType', 'unknown')} | "
            f"{processing_time:.3f}s"
        )

        # Extract processing time from handler's result (if available in processing_info)
        if "processing_info" in result and "processing_time_seconds" in result["processing_info"]:
            result["processing_time"] = result["processing_info"]["processing_time_seconds"]
        else:
            # Fallback: use our measured time if handler doesn't provide it
            result["processing_time"] = processing_time

        return result

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Classification failed: {file.name} | {str(e)}", exc_info=True)
        return {
            "service": "Document Classification",
            "error": f"Classification failed: {str(e)}",
            "processing_time": processing_time,
            "docType": "unknown",
            "confidence": 0.0,
        }


async def process_document_parallel(file, service_name: str, service_class) -> dict[str, Any]:
    """
    Run classification and extraction in parallel, then consolidate results.

    Args:
        file: File to process
        service_name: Name of the extraction service
        service_class: Service class to instantiate

    Returns:
        Consolidated results with classification and extraction data
    """
    overall_start_time = time.time()

    # Run classification and extraction in parallel
    classification_task = classify_document_async(file)
    extraction_task = extract_with_service_async(service_name, service_class, file)

    # Wait for both tasks to complete
    classification_result, extraction_result = await asyncio.gather(
        classification_task, extraction_task, return_exceptions=True
    )

    # Handle exceptions from gather
    if isinstance(classification_result, Exception):
        classification_result = {
            "service": "Document Classification",
            "error": f"Classification failed: {str(classification_result)}",
            "processing_time": 0.0,
            "docType": "unknown",
            "confidence": 0.0,
        }

    if isinstance(extraction_result, Exception):
        extraction_result = {
            "service": service_name,
            "error": f"Extraction failed: {str(extraction_result)}",
            "processing_time": 0.0,
        }

    # Calculate overall processing time (max of both operations)
    classification_time = classification_result.get("processing_time", 0.0)
    extraction_time = extraction_result.get("processing_time", 0.0)
    overall_processing_time = time.time() - overall_start_time

    # Log the parallel execution results
    logger.info(
        f"Parallel processing completed: {file.name} | "
        f"Classification: {classification_time:.3f}s | "
        f"Extraction: {extraction_time:.3f}s | "
        f"Overall: {overall_processing_time:.3f}s"
    )

    # Validate classification result
    is_classification_valid = (
        "error" not in classification_result and classification_result.get("docType") != "unknown"
    )

    # Build consolidated result
    consolidated_result = {
        "classification": classification_result,
        "extraction": extraction_result,
        "is_valid_document": is_classification_valid,
        "overall_processing_time": overall_processing_time,
        "classification_time": classification_time,
        "extraction_time": extraction_time,
    }

    return consolidated_result


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
    if "prefill_selected_service_display" not in st.session_state:
        st.session_state.prefill_selected_service_display = DEFAULT_SERVICE

    if "prefill_uploaded_file_name" not in st.session_state:
        st.session_state.prefill_uploaded_file_name = None

    if "prefill_invalid_file_name" not in st.session_state:
        st.session_state.prefill_invalid_file_name = None

    if "prefill_consolidated_result" not in st.session_state:
        st.session_state.prefill_consolidated_result = None

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

    st.title("📝 Demo Form Pre-Fill")
    st.markdown(
        """
    <div style="text-align: center; margin-bottom: 2rem;">
        <p style="font-size: 1.2rem; color: var(--text-secondary);">
            Upload a document and select an extraction service to automatically pre-fill the form below
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Initialize session state
    initialize_session_state()

    # Section 1 & 2: Upload Document and Select Extraction Service
    with st.container(border=True):
        col_service, col_upload = st.columns(2, gap="medium")

        # LEFT COLUMN: Select Extraction Service
        with col_service:
            st.subheader("1️⃣ Select Extraction Service")

            selected_service_display = st.selectbox(
                "Choose an extraction service",
                options=list(SERVICE_CONFIG.keys()),
                index=(list(SERVICE_CONFIG.keys())).index(
                    st.session_state.prefill_selected_service_display
                )
                if st.session_state.prefill_selected_service_display in list(SERVICE_CONFIG.keys())
                else 0,
                key="prefill_service_selector",
            )

            # Update display state
            st.session_state.prefill_selected_service_display = selected_service_display

        # RIGHT COLUMN: Upload Document
        with col_upload:
            st.subheader("2️⃣ Upload Document")
            uploaded_file = st.file_uploader(
                "Choose a file (PDF or image)",
                type=["pdf", "png", "jpg", "jpeg"],
                key="prefill_file_uploader",
            )

            # Validate and handle uploaded file
            if uploaded_file and not is_valid_file_type(uploaded_file):
                st.error("❌ Invalid file type. Please upload PDF, PNG, JPG, or JPEG files only.")

    # Get current uploaded file from uploader widget
    uploaded_file = st.session_state.get("prefill_file_uploader")
    has_valid_file = uploaded_file is not None and is_valid_file_type(uploaded_file)

    # Section 3: Auto-trigger parallel processing when a new file is uploaded
    if uploaded_file:
        # Check if file is already marked as invalid (regardless of if it's new)
        if uploaded_file.name == st.session_state.prefill_invalid_file_name:
            # File was previously marked as invalid - show persistent warning and skip processing
            st.warning(
                f"⚠️ **File Previously Invalid**\n\n"
                f"The file `{uploaded_file.name}` was previously rejected due to validation issues. "
                f"Please upload a different valid document or ensure the file meets requirements."
            )
            # Don't proceed with processing for previously invalid files
        elif uploaded_file.name != st.session_state.prefill_uploaded_file_name:
            # New file detected - process it
            if not has_valid_file:
                # New file is invalid - mark it and show error
                st.session_state.prefill_invalid_file_name = uploaded_file.name
                st.error(
                    f"❌ **Invalid File Uploaded**\n\n"
                    f"The file `{uploaded_file.name}` is not valid for processing. "
                    f"Please upload a valid PDF, PNG, JPG, or JPEG file."
                )
                # Reset consolidated result
                st.session_state.prefill_consolidated_result = None
            else:
                # Valid file - proceed with parallel processing
                service_name, service_class = SERVICE_CONFIG[
                    st.session_state.prefill_selected_service_display
                ]

                with st.spinner(
                    "⏳ Processing document (Classification + Extraction in parallel)..."
                ):
                    try:
                        # Run classification and extraction in parallel
                        consolidated_result = asyncio.run(
                            process_document_parallel(uploaded_file, service_name, service_class)
                        )

                        # Store consolidated result
                        st.session_state.prefill_consolidated_result = consolidated_result
                        st.session_state.prefill_uploaded_file_name = uploaded_file.name

                        # Extract classification and extraction results
                        classification_result = consolidated_result.get("classification", {})
                        extraction_result = consolidated_result.get("extraction", {})
                        is_valid_document = consolidated_result.get("is_valid_document", False)
                        overall_time = consolidated_result.get("overall_processing_time", 0.0)
                        classification_time = consolidated_result.get("classification_time", 0.0)
                        extraction_time = consolidated_result.get("extraction_time", 0.0)

                        # Show processing time summary
                        st.info(
                            f"⏱️ **Processing Time Summary:**\n\n"
                            f"- Classification: {classification_time:.3f}s\n"
                            f"- Extraction: {extraction_time:.3f}s\n"
                            f"- **Overall (Parallel): {overall_time:.3f}s**"
                        )

                        # Check classification validity first
                        if "error" in classification_result:
                            st.error(
                                f"❌ Classification failed: "
                                f"{classification_result.get('error', 'Unknown error')}"
                            )
                            st.session_state.prefill_invalid_file_name = uploaded_file.name
                        elif not is_valid_document:
                            # Invalid document type (unknown)
                            doc_type = classification_result.get("docType", "unknown")
                            confidence = classification_result.get("confidence", 0.0)
                            st.error(
                                f"❌ **Invalid Document Type Detected**\n\n"
                                f"The uploaded document could not be classified. "
                                f"Please upload a valid document.\n\n"
                                f"**Type:** {doc_type} | **Confidence:** {confidence:.2%}"
                            )
                            st.session_state.prefill_invalid_file_name = uploaded_file.name
                        else:
                            # Valid document - show classification success
                            doc_type = classification_result.get("docType", "unknown")
                            confidence = classification_result.get("confidence", 0.0)
                            st.success(
                                f"✅ Document classified as: **{doc_type}** "
                                f"(confidence: {confidence:.2%})"
                            )

                            # Check extraction results and populate form if valid document
                            if "error" in extraction_result:
                                st.error(
                                    f"❌ Extraction failed: "
                                    f"{extraction_result.get('error', 'Unknown error')}"
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
                                st.session_state.prefill_form_data["tradeName"] = (
                                    extract_field_value(extraction_result, "tradeName")
                                )
                                st.session_state.prefill_form_data["businessType"] = (
                                    extract_field_value(extraction_result, "businessType")
                                )

                                st.success("✅ Form pre-filled successfully!")

                    except Exception as e:
                        logger.error(f"Parallel processing error: {str(e)}", exc_info=True)
                        st.error(f"❌ Processing failed: {str(e)}")
                        st.session_state.prefill_consolidated_result = None
                        st.session_state.prefill_invalid_file_name = uploaded_file.name

    # Section 4: Display Form (always visible, pre-filled after extraction)
    st.markdown("---")
    st.subheader("📋 Document Information Form")

    # Show extraction info if available
    consolidated_result = st.session_state.prefill_consolidated_result
    if consolidated_result and consolidated_result.get("is_valid_document", False):
        extraction_result = consolidated_result.get("extraction", {})
        if extraction_result and "error" not in extraction_result:
            uploaded_file = st.session_state.get("prefill_file_uploader")
            file_name = uploaded_file.name if uploaded_file else "Unknown"
            overall_time = consolidated_result.get("overall_processing_time", 0.0)
            st.caption(
                f"🔍 Extracted from **{file_name}** "
                f"using **{st.session_state.prefill_selected_service_display}** "
                f"in {overall_time:.3f}s (parallel processing)"
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
            disabled=True,
        )

        st.text_input(
            "Taxpayer Name",
            value=st.session_state.prefill_form_data.get("taxpayerName", ""),
            placeholder="Enter taxpayer name",
            help="Full name of the taxpayer or business entity",
            disabled=True,
        )

        st.text_input(
            "Registered Date",
            value=st.session_state.prefill_form_data.get("registeredDate", ""),
            placeholder="MM/DD/YYYY",
            help="Date the TIN was issued or registered",
            disabled=True,
        )

        st.text_input(
            "Trade Name",
            value=st.session_state.prefill_form_data.get("tradeName", ""),
            placeholder="Enter trade name",
            help="Registered trade name or business name",
            disabled=True,
        )

        st.text_input(
            "Business Type",
            value=st.session_state.prefill_form_data.get("businessType", ""),
            placeholder="Enter business type",
            help="Line of business or business activities",
            disabled=True,
        )

        st.text_area(
            "Registered Address",
            value=st.session_state.prefill_form_data.get("registeredAddress", ""),
            placeholder="Enter complete registered address",
            help="Complete registered address of the taxpayer or business",
            disabled=True,
        )

    # RIGHT COLUMN: File preview
    with col_preview:
        uploaded_file = st.session_state.get("prefill_file_uploader")
        if uploaded_file:
            with st.container(border=True):
                st.markdown("**📄 Document Preview**")

                file_name = uploaded_file.name
                file_extension = file_name.lower().split(".")[-1]

                try:
                    if file_extension == "pdf":
                        # For PDF files, render all pages in tabs
                        pdf_bytes = uploaded_file.getvalue()
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
                            uploaded_file,
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
