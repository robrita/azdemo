# pages/6_Document_Extraction.py
import streamlit as st
import pandas as pd
import sys
import os
import json
import asyncio
import concurrent.futures
import time
from datetime import datetime
sys.path.append('..')
from utils import render_sidebar, keep_state

# Import plotly for performance analytics (lazy import in repository section)
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# Import extraction service classes (implementations should be in handlers/)
from handlers.document_intelligence import DocumentIntelligence
from handlers.content_understanding import ContentUnderstanding
from handlers.mistral_document_ai import MistralDocumentAI
from handlers.gpt5_vision import GPT5ForVision
from handlers.gpt41_vision import GPT41ForVision

def is_valid_file_type(file):
    """Check if uploaded file has a valid type for document extraction."""
    allowed_types = ['pdf', 'png', 'jpg', 'jpeg']
    if file is not None and hasattr(file, 'name'):
        file_extension = file.name.lower().split('.')[-1]
        return file_extension in allowed_types
    return False

def get_file_type_description(file):
    """Get a user-friendly description of the file type."""
    if file is not None and hasattr(file, 'name'):
        file_extension = file.name.lower().split('.')[-1]
        type_map = {
            'pdf': 'PDF Document',
            'png': 'PNG Image',
            'jpg': 'JPEG Image', 
            'jpeg': 'JPEG Image'
        }
        return type_map.get(file_extension, f'{file_extension.upper()} File')
    return 'Unknown File Type'

async def extract_with_service_async(svc_name, svc_class, file, progress_callback=None):
    """
    Asynchronously extract data using a specific service.
    
    Args:
        svc_name: Name of the service
        svc_class: Service class to instantiate
        file: File to process
        progress_callback: Optional callback to report progress
        
    Returns:
        Tuple of (service_name, extraction_result, processing_time)
    """
    start_time = time.time()
    
    try:
        # Run the potentially blocking extraction in a thread pool
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Create service instance and run extraction in executor
            svc = svc_class(svc_name)
            result = await loop.run_in_executor(executor, svc.extract, file)
        
        processing_time = time.time() - start_time
        
        # Call progress callback if provided
        if progress_callback:
            progress_callback(svc_name, True, processing_time)
            
        return svc_name, result, processing_time
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_result = {
            "service": svc_name,
            "error": f"Async extraction failed: {str(e)}",
            "processing_time": processing_time
        }
        
        # Call progress callback if provided
        if progress_callback:
            progress_callback(svc_name, False, processing_time)
            
        return svc_name, error_result, processing_time

async def process_file_with_services_async(file, selected_services, progress_container=None):
    """
    Process a single file with multiple services in parallel.
    
    Args:
        file: File to process
        selected_services: List of (service_name, service_class) tuples
        progress_container: Streamlit container for progress updates
        
    Returns:
        Dictionary of service results
    """
    # Create progress tracking
    service_status = {svc_name: "⏳ Pending" for svc_name, _ in selected_services}
    
    if progress_container:
        progress_placeholder = progress_container.empty()
        
        def update_progress(svc_name, success, proc_time):
            if success:
                service_status[svc_name] = f"✅ Complete ({proc_time:.1f}s)"
            else:
                service_status[svc_name] = f"❌ Failed ({proc_time:.1f}s)"
            
            # Update progress display
            progress_text = "\n".join([f"**{svc}**: {status}" 
                                     for svc, status in service_status.items()])
            progress_placeholder.markdown(f"**Processing Status:**\n\n{progress_text}")
    else:
        update_progress = None
    
    # Create tasks for all services
    tasks = []
    for svc_name, svc_class in selected_services:
        task = extract_with_service_async(svc_name, svc_class, file, update_progress)
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
        "parallel_speedup": f"{total_time/len(selected_services) if selected_services else 0:.2f}s avg per service"
    }
    
    return file_results

def main():
    render_sidebar()
    st.header("📑 Document Extraction")

    tab1, tab2 = st.tabs(["📤 Upload & Extract", "📚 Document Repository"])

    with tab1:
        st.subheader("Upload Documents for Extraction")
        uploaded_files = st.file_uploader(
            "Choose files (PDF or images)",
            type=['pdf', 'png', 'jpg', 'jpeg'],
            accept_multiple_files=True
        )
        st.caption("Supported: PDF, PNG, JPG, JPEG - Multiple files allowed")

        st.markdown("**Select Extraction Services:**")
        col1, col2 = st.columns(2)
        with col1:
            svc_template = st.checkbox("Document Intelligence - Template", 
                                     value=st.session_state.get("svc_template", False))
            svc_neural = st.checkbox("Document Intelligence - Neural", 
                                   value=st.session_state.get("svc_neural", False))
            svc_content = st.checkbox("Content Understanding", 
                                    value=st.session_state.get("svc_content", False))
        with col2:
            svc_mistral = st.checkbox("Mistral Document AI", 
                                    value=st.session_state.get("svc_mistral", False))
            svc_gpt5 = st.checkbox("GPT-5 for Vision", 
                                 value=st.session_state.get("svc_gpt5", False))
            svc_gpt41 = st.checkbox("GPT-4.1 for Vision", 
                                  value=st.session_state.get("svc_gpt41", False))

        # Store checkbox states in session
        st.session_state["svc_template"] = svc_template
        st.session_state["svc_neural"] = svc_neural
        st.session_state["svc_content"] = svc_content
        st.session_state["svc_mistral"] = svc_mistral
        st.session_state["svc_gpt5"] = svc_gpt5
        st.session_state["svc_gpt41"] = svc_gpt41

        selected_services = []
        if svc_template:
            selected_services.append(("ADI-Template", DocumentIntelligence))
        if svc_neural:
            selected_services.append(("ADI-Neural", DocumentIntelligence))
        if svc_content:
            selected_services.append(("Content-Understanding", ContentUnderstanding))
        if svc_mistral:
            selected_services.append(("Mistral-Doc-AI", MistralDocumentAI))
        if svc_gpt5:
            selected_services.append(("GPT-5-Vision", GPT5ForVision))
        if svc_gpt41:
            selected_services.append(("GPT-4.1-Vision", GPT41ForVision))

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
            with col_files:
                with st.expander("📂 Stored Files", expanded=False):
                    for i, file in enumerate(valid_files):
                        st.write(f"{i+1}. **{file.name}** ({get_file_type_description(file)})")
            
            with col_clear_files:
                if st.button("🗑️ Clear Files"):
                    if "valid_files" in st.session_state:
                        del st.session_state["valid_files"]
                    st.rerun()
        else:
            valid_files = []
        
        # Show guidance when files are ready but no services selected
        if valid_files and not selected_services:
            st.info("💡 Please select at least one extraction service above to enable document processing.")
        
        # Only show Extract button if files are valid AND services are selected
        if valid_files and selected_services and st.button("🚀 Extract Documents"):
            # No need to check for selected_services again since button only shows when services are selected
            with st.spinner(f"Extracting {len(valid_files)} document(s) with {len(selected_services)} services in parallel..."):
                os.makedirs("outputs", exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Overall progress tracking
                overall_start_time = time.time()
                
                # Process each valid file with async parallel processing
                for i, file in enumerate(valid_files):
                    # Create progress container for this file
                    progress_container = st.container()
                    
                    # Run async processing for this file
                    try:
                        # Run the async function in Streamlit
                        file_results = asyncio.run(
                            process_file_with_services_async(file, selected_services, progress_container)
                        )
                        
                        # Extract processing summary
                        processing_summary = file_results.pop("_processing_summary", {})
                        
                        # Display processing performance metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Services", processing_summary.get("total_services", 0))
                        with col2:
                            st.metric("Successful", processing_summary.get("successful_services", 0), 
                                    delta=f"+{processing_summary.get('successful_services', 0)}")
                        with col3:
                            st.metric("Failed", processing_summary.get("failed_services", 0),
                                    delta=f"-{processing_summary.get('failed_services', 0)}" if processing_summary.get("failed_services", 0) > 0 else None)
                        with col4:
                            file_overall_time = time.time() - overall_start_time
                            st.metric("Processing Time", f"{file_overall_time:.2f}s")
                        
                        # Display results for this file
                        with st.expander(f"📄 Results for {file.name}", expanded=False):
                            # Show successful extractions
                            successful_results = {k: v for k, v in file_results.items() 
                                                if isinstance(v, dict) and "error" not in v}
                            failed_results = {k: v for k, v in file_results.items() 
                                            if isinstance(v, dict) and "error" in v}
                            
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
                        st.error(f"❌ Failed to process {file.name}: {str(e)}")
                        continue
                
    with tab2:
        st.subheader("Document Repository")
        repo = []
        if os.path.exists("outputs"):
            for fname in os.listdir("outputs"):
                if fname.endswith(".json"):
                    with open(os.path.join("outputs", fname), "r", encoding="utf-8") as f:
                        try:
                            data = json.load(f)
                            processing_summary = data.get("processing_summary", {})
                            results = data.get("results", {})
                            
                            # Count successful vs failed extractions
                            successful_count = processing_summary.get("successful_services", 
                                len([r for r in results.values() if isinstance(r, dict) and "error" not in r]))
                            total_services = processing_summary.get("total_services", len(data.get("services", [])))
                            
                            repo.append({
                                "File Name": data.get("file_name", fname),
                                "File Type": data.get("file_type", "-"),
                                "Timestamp": data.get("timestamp", "-"),
                                "Services": f"{total_services} services",
                                "Success Rate": f"{successful_count}/{total_services}" if total_services > 0 else "-",
                                "Result Keys": ", ".join(results.keys()) if results else "-",
                                "File": fname
                            })
                        except Exception:
                            continue
        
        if repo:
            df = pd.DataFrame(repo)
            
            # Display enhanced repository table
            st.dataframe(df, width='stretch', hide_index=True)
            
            # Show repository statistics
            if len(repo) > 0:
                col1, col2, col3, col4 = st.columns(4)
                
                total_files = len(repo)
                avg_services = sum([int(r["Services"].split()[0]) for r in repo if r["Services"] != "-"]) / total_files if total_files > 0 else 0
                
                # Calculate success rates
                success_rates = []
                for r in repo:
                    if r["Success Rate"] != "-" and "/" in r["Success Rate"]:
                        success, total = map(int, r["Success Rate"].split("/"))
                        if total > 0:
                            success_rates.append(success / total * 100)
                
                avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0
                
                with col1:
                    st.metric("Total Documents", total_files)
                with col2:
                    st.metric("Avg Services/Doc", f"{avg_services:.1f}")
                with col3:
                    st.metric("Avg Success Rate", f"{avg_success_rate:.1f}%")
                with col4:
                    total_extractions = sum([int(r["Services"].split()[0]) for r in repo if r["Services"] != "-"])
                    st.metric("Total Extractions", total_extractions)
        else:
            st.info("No extracted documents found.")

if __name__ == "__main__":
    main()
