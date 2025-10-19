# pages/6_Document_Extraction.py
import asyncio
import concurrent.futures
import json
import logging
import os
import sys
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.append("..")
from dotenv import load_dotenv

from handlers.content_understanding import ContentUnderstanding

# Import extraction service classes (implementations should be in handlers/)
from handlers.document_intelligence import DocumentIntelligence
from handlers.gpt_vision import GPTForVision
from handlers.mistral_document_ai import MistralDocumentAI
from utils import keep_state, render_sidebar

# Load environment variables
load_dotenv()


# Configure logging with custom formatter to show milliseconds
class MillisecondFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):  # noqa: N802
        # Get the base time format
        ct = self.converter(record.created)
        s = time.strftime(datefmt, ct) if datefmt else time.strftime("%Y-%m-%d %H:%M:%S", ct)
        # Append milliseconds
        s = f"{s}.{int(record.msecs):03d}"
        return s


# Create formatter instance
formatter = MillisecondFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Configure logging
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)

# Suppress verbose Azure SDK logging
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def is_valid_file_type(file):
    """Check if uploaded file has a valid type for document extraction."""
    allowed_types = ["pdf", "png", "jpg", "jpeg"]
    if file is not None and hasattr(file, "name"):
        file_extension = file.name.lower().split(".")[-1]
        return file_extension in allowed_types
    return False


def get_file_type_description(file):
    """Get a user-friendly description of the file type."""
    if file is not None and hasattr(file, "name"):
        file_extension = file.name.lower().split(".")[-1]
        type_map = {
            "pdf": "PDF Document",
            "png": "PNG Image",
            "jpg": "JPEG Image",
            "jpeg": "JPEG Image",
        }
        return type_map.get(file_extension, f"{file_extension.upper()} File")
    return "Unknown File Type"


async def extract_with_service_async(svc_name, svc_class, file):
    """
    Asynchronously extract data using a specific service.

    Args:
        svc_name: Name of the service
        svc_class: Service class to instantiate
        file: File to process

    Returns:
        Tuple of (service_name, extraction_result, processing_time)
    """
    start_time = time.time()

    try:
        # Run the potentially blocking extraction in a thread pool
        loop = asyncio.get_event_loop()
        # Suppress ScriptRunContext warnings in thread pool
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

        return svc_name, result, processing_time

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Extraction failed: {svc_name} | {file.name} | {str(e)}", exc_info=True)
        error_result = {
            "service": svc_name,
            "error": f"Async extraction failed: {str(e)}",
            "processing_time": processing_time,
        }

        return svc_name, error_result, processing_time


async def process_file_with_services_async(file, selected_services):
    """
    Process a single file with multiple services in parallel.

    Args:
        file: File to process
        selected_services: List of (service_name, service_class) tuples

    Returns:
        Dictionary of service results
    """
    # Create tasks for all services
    tasks = []
    for svc_name, svc_class in selected_services:
        task = extract_with_service_async(svc_name, svc_class, file)
        tasks.append(task)

    # Run all services in parallel and gather results
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results into a dictionary
    file_results = {}
    total_time = 0
    successful_services = 0

    for result in results:
        if isinstance(result, Exception):
            # Handle any unexpected exceptions
            logger.error(f"Parallel extraction exception: {str(result)}")
            file_results["Unknown Service"] = {"error": f"Unexpected error: {str(result)}"}
        else:
            svc_name, extraction, proc_time = result
            file_results[svc_name] = extraction
            total_time += proc_time

            # Check if extraction was successful (no error key)
            if isinstance(extraction, dict) and "error" not in extraction:
                successful_services += 1

    # Add processing summary
    file_results["_processing_summary"] = {
        "total_services": len(selected_services),
        "successful_services": successful_services,
        "failed_services": len(selected_services) - successful_services,
        "parallel_speedup": f"{total_time / len(selected_services) if selected_services else 0:.2f}s avg per service",
    }

    return file_results


def main():
    logger.info("Document Extraction application started")
    render_sidebar()
    st.header("📑 Document Extraction")

    tab1, tab2 = st.tabs(["📤 Upload & Extract", "🔍 Analyze Output"])

    with tab1:
        st.subheader("Upload Documents for Extraction")
        uploaded_files = st.file_uploader(
            "Choose files (PDF or images)",
            type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
        )
        st.caption("Supported: PDF, PNG, JPG, JPEG - Multiple files allowed")

        st.markdown("**Select Extraction Services:**")
        col1, col2 = st.columns(2)
        with col1:
            svc_template = st.checkbox(
                "Document Intelligence - Template",
                value=st.session_state.get("svc_template", False),
            )
            svc_neural = st.checkbox(
                "Document Intelligence - Neural", value=st.session_state.get("svc_neural", False)
            )
            svc_content = st.checkbox(
                "Content Understanding", value=st.session_state.get("svc_content", False)
            )
        with col2:
            svc_mistral = st.checkbox(
                "Mistral Document AI", value=st.session_state.get("svc_mistral", False)
            )
            svc_gpt41 = st.checkbox(
                "GPT-4.1 for Vision", value=st.session_state.get("svc_gpt41", False)
            )
            svc_gpt5 = st.checkbox(
                "GPT-5 for Vision", value=st.session_state.get("svc_gpt5", False)
            )

        # Store checkbox states in session
        st.session_state["svc_template"] = svc_template
        st.session_state["svc_neural"] = svc_neural
        st.session_state["svc_content"] = svc_content
        st.session_state["svc_mistral"] = svc_mistral
        st.session_state["svc_gpt41"] = svc_gpt41
        st.session_state["svc_gpt5"] = svc_gpt5

        selected_services = []
        if svc_template:
            selected_services.append(("ADI-Template", DocumentIntelligence))
        if svc_neural:
            selected_services.append(("ADI-Neural", DocumentIntelligence))
        if svc_content:
            selected_services.append(("Content-Understanding", ContentUnderstanding))
        if svc_mistral:
            selected_services.append(("Mistral-Doc-AI", MistralDocumentAI))
        if svc_gpt41:
            selected_services.append(("GPT-4.1-Vision", GPTForVision))
        if svc_gpt5:
            selected_services.append(("GPT-5-Vision", GPTForVision))

        # Use keep_state to persist selected_services across page navigation
        keep_state(selected_services, "selected_services")

        # Check for stored valid files from session state
        stored_valid_files = st.session_state.get("valid_files", [])

        if uploaded_files:
            # Validate file types and show upload summary
            valid_files = []
            invalid_files = []

            for file in uploaded_files:
                if is_valid_file_type(file):
                    valid_files.append(file)
                else:
                    invalid_files.append(file)

            # Use keep_state to persist valid_files across page navigation
            keep_state(valid_files, "valid_files")

            # Display file validation results
            if valid_files:
                st.success(f"✅ {len(valid_files)} valid file(s) uploaded successfully!")

            if invalid_files:
                st.error(f"❌ {len(invalid_files)} invalid file(s) detected!")
                with st.expander("⚠️ Invalid Files"):
                    for file in invalid_files:
                        st.write(f"• **{file.name}** - Unsupported file type")
                    st.caption("Only PDF, PNG, JPG, and JPEG files are supported.")

        # Handle stored files from session state
        elif stored_valid_files:
            valid_files = stored_valid_files
            st.info(f"📁 Using {len(valid_files)} previously uploaded file(s) from session")

            # Show stored files with option to clear
            col_files, col_clear_files = st.columns([3, 1])
            with col_files, st.expander("📂 Stored Files", expanded=False):
                for i, file in enumerate(valid_files):
                    st.write(f"{i + 1}. **{file.name}** ({get_file_type_description(file)})")

            with col_clear_files:
                if st.button("🗑️ Clear Files"):
                    if "valid_files" in st.session_state:
                        del st.session_state["valid_files"]
                    st.rerun()
        else:
            valid_files = []

        # Show guidance when files are ready but no services selected
        if valid_files and not selected_services:
            st.info(
                "💡 Please select at least one extraction service above to enable document processing."
            )

        # Only show Extract button if files are valid AND services are selected
        if valid_files and selected_services and st.button("🚀 Extract Documents"):
            logger.info(
                f"Extraction started: {len(valid_files)} files x {len(selected_services)} services"
            )
            with st.spinner(
                f"Extracting {len(valid_files)} document(s) with {len(selected_services)} services in parallel..."
            ):
                os.makedirs("outputs", exist_ok=True)

                # Process each valid file with async parallel processing
                for file in valid_files:
                    # Run async processing for this file
                    try:
                        # Run the async function in Streamlit
                        file_results = asyncio.run(
                            process_file_with_services_async(file, selected_services)
                        )

                        # Remove processing summary from results
                        file_results.pop("_processing_summary", {})

                        # Display results for this file
                        with st.expander(f"📄 Results for {file.name}", expanded=False):
                            # Show successful extractions
                            successful_results = {
                                k: v
                                for k, v in file_results.items()
                                if isinstance(v, dict) and "error" not in v
                            }
                            failed_results = {
                                k: v
                                for k, v in file_results.items()
                                if isinstance(v, dict) and "error" in v
                            }

                            if successful_results:
                                st.markdown("**✅ Successful Extractions:**")
                                for svc_name, extraction in successful_results.items():
                                    with st.expander(f"🔍 {svc_name}", expanded=False):
                                        st.json(extraction)

                            if failed_results:
                                st.markdown("**❌ Failed Extractions:**")
                                for svc_name, extraction in failed_results.items():
                                    with st.expander(f"⚠️ {svc_name} (Error)", expanded=False):
                                        st.error(extraction.get("error", "Unknown error"))
                                        st.json(extraction)

                    except Exception as e:
                        logger.error(
                            f"File extraction error: {file.name} | {str(e)}", exc_info=True
                        )
                        st.error(f"❌ Failed to process {file.name}: {str(e)}")
                        continue

    with tab2:
        st.subheader("Analyze Output")

        # Load JSON data from outputs folder
        json_files = []
        if os.path.exists("outputs"):
            json_files = [f for f in os.listdir("outputs") if f.endswith(".json")]

        if not json_files:
            st.info("No extraction results found in outputs folder.")
        else:
            # Allow user to select which JSON file to analyze
            selected_json = st.selectbox("Select JSON file to analyze", json_files, index=0)

            if selected_json:
                json_path = os.path.join("outputs", selected_json)

                try:
                    with open(json_path, encoding="utf-8") as f:
                        data = json.load(f)

                    # Extract results array from JSON
                    results = data.get("results", [])

                    logger.info(f"Loaded {len(results)} result(s) from {selected_json}")

                    if not results:
                        st.warning("No results found in the selected JSON file.")
                    else:
                        # Add filter to select value or confidence view
                        view_type = st.selectbox("Select data view", ["Values", "Confidence"])

                        # Prepare data for tables
                        table_data = []

                        # Dynamically collect all field names across results (exclude language, summary)
                        dynamic_field_names = set()
                        for result in results:
                            for field in result.get("fields", []):
                                fname = field.get("name", "")
                                if fname and fname not in ("language", "summary"):
                                    dynamic_field_names.add(fname)

                        # Sort for consistent column ordering
                        dynamic_field_names = sorted(dynamic_field_names)

                        for result in results:
                            file_name = result.get("file_name", "")
                            service_name = result.get("service_name", "")
                            processing_time = result.get("processing_time", 0.0)

                            # Base row with required metadata
                            row = {
                                "file_name": file_name,
                                "service_name": service_name,
                                "processing_time": f"{processing_time:.3f}s"
                                if processing_time
                                else "0.000s",
                            }

                            # Initialize dynamic fields as empty
                            for fname in dynamic_field_names:
                                row[fname] = ""

                            # Populate values or confidence
                            for field in result.get("fields", []):
                                field_name = field.get("name", "")
                                if field_name in row and field_name not in ("language", "summary"):
                                    if view_type == "Values":
                                        row[field_name] = field.get("value", "")
                                    else:  # Confidence view
                                        confidence = field.get("confidence", 0)
                                        row[field_name] = f"{confidence:.3f}" if confidence else ""

                            table_data.append(row)

                        # Create DataFrame and sort by file_name, then service_name
                        df = pd.DataFrame(table_data)
                        df = df.sort_values(
                            by=["file_name", "service_name"], ascending=True
                        ).reset_index(drop=True)

                        # Display the table
                        st.markdown(f"### {view_type} Table")
                        st.dataframe(df, width="stretch", hide_index=True)

                        # Add Processing Time Trends Graph
                        st.markdown("---")
                        st.markdown("### Processing Time Trends")

                        # Prepare data for line chart
                        # Group by file_name and service_name, get processing times
                        chart_data = []
                        for result in results:
                            file_name = result.get("file_name", "")
                            service_name = result.get("service_name", "")
                            processing_time = result.get("processing_time", 0.0)
                            chart_data.append(
                                {
                                    "file_name": file_name,
                                    "service_name": service_name,
                                    "processing_time": processing_time,
                                }
                            )

                        chart_df = pd.DataFrame(chart_data)

                        # Get unique services
                        services = sorted(chart_df["service_name"].unique())

                        # Create line chart with a line for each service
                        fig = go.Figure()

                        # Color palette for services
                        colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"]

                        for idx, service in enumerate(services):
                            service_data = chart_df[chart_df["service_name"] == service]
                            # Sort by file_name to ensure proper line connection
                            service_data = service_data.sort_values("file_name")

                            fig.add_trace(
                                go.Scatter(
                                    x=service_data["file_name"],
                                    y=service_data["processing_time"],
                                    mode="lines+markers",
                                    name=service,
                                    line={"color": colors[idx % len(colors)], "width": 2},
                                    marker={"size": 8},
                                )
                            )

                        fig.update_layout(
                            hovermode="x unified",
                            xaxis_title="File Name",
                            yaxis_title="Processing Time (seconds)",
                            yaxis={"rangemode": "tozero", "dtick": 2},
                            legend={
                                "orientation": "h",
                                "yanchor": "bottom",
                                "y": 1.02,
                                "xanchor": "right",
                                "x": 1,
                            },
                            height=400,
                        )

                        st.plotly_chart(fig, config={"responsive": True})

                except Exception as e:
                    logger.error(f"JSON load error: {json_path} | {str(e)}", exc_info=True)
                    st.error(f"Error loading JSON file: {str(e)}")


if __name__ == "__main__":
    main()
