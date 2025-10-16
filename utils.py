import streamlit as st

def render_sidebar():
    """
    Render the common sidebar navigation for all pages in the Document Processing application.
    This function should be called on every page to maintain consistent navigation.
    """
    # Configure page
    st.set_page_config(
        page_title="Document Processing Dashboard",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.logo(
        "https://devblogs.microsoft.com/foundry/wp-content/uploads/sites/89/2025/03/ai-foundry.png",
        link="https://ai.azure.com/",
    )

    # Loading the CSS
    with open('style.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

    with st.sidebar:
        with st.container(border=True):
            st.page_link("app.py", label="Home", icon="🏠")
            st.page_link("pages/1_Document_Extraction.py", label="Document Extraction", icon="📑")

        st.image(
            "https://miro.medium.com/1*zBt3FbYHV2-CWcBnkYoQRA.png",
        )
        st.write("Powered by Azure AI Foundry.")


def keep_state(state_object, state_name):
    """
    Keep the Streamlit session state alive across page navigations.
    This is useful to maintain stateful data like uploaded files or user inputs.
    """
    if state_object:
        st.session_state[state_name] = state_object
    elif state_name in st.session_state:
        return True
    return False

def save_extraction_to_json(file_name: str, service_name: str, pages_count: int, fields: dict, overall_confidence: float = None, processing_time: float = None, results_file_path: str = "outputs/extract_results.json") -> None:
    """
    Save extraction results to JSON file following standardized structure.
    This function handles loading existing data, filtering by file_name and service_name,
    and updating or appending new results.
    
    Args:
        file_name: Name of the processed file
        service_name: Name of the extraction service used
        pages_count: Number of pages in the document
        fields: Dictionary of extracted fields with confidence scores and content
        overall_confidence: Overall document confidence score (if None, defaults to 0.0)
        processing_time: Time taken to process the file in seconds (if None, defaults to 0.0)
        results_file_path: Path to the JSON results file (default: outputs/extract_results.json)
    """
    import json
    from pathlib import Path
    
    try:
        results_file = Path(results_file_path)
        
        # Ensure outputs directory exists
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing data or create new structure
        if results_file.exists():
            with open(results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {"results": []}
        
        # Build fields array with name, value, and confidence
        fields_array = []
        
        for field_name, field_data in fields.items():
            # Extract value from content (or fallback to value or empty string)
            value = field_data.get('content', field_data.get('value', ''))
            confidence = field_data.get('confidence', 0.0)
            
            fields_array.append({
                "name": field_name,
                "value": value,
                "confidence": round(confidence, 3)
            })

        # Use provided overall_confidence or default to 0.0
        document_confidence = round(overall_confidence, 3) if overall_confidence is not None else 0.0
        
        # Use provided processing_time or default to 0.0
        proc_time = round(processing_time, 3) if processing_time is not None else 0.0
        
        # Create new result entry
        new_result = {
            "file_name": file_name,
            "service_name": service_name,
            "pages_count": pages_count,
            "document_confidence": document_confidence,
            "processing_time": proc_time,
            "fields": fields_array
        }
        
        # Find and update existing entry or append new one
        existing_index = None
        for idx, result in enumerate(data["results"]):
            if result.get("file_name") == file_name and result.get("service_name") == service_name:
                existing_index = idx
                break
        
        if existing_index is not None:
            # Update existing entry
            data["results"][existing_index] = new_result
        else:
            # Append new entry
            data["results"].append(new_result)
        
        # Save back to file
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        st.warning(f"Failed to save results to JSON: {str(e)}")
        print(f"Error details: {e}")
