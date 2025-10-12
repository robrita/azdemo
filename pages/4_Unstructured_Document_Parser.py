# pages/4_Unstructured_Document_Parser.py
import os, sys, json
import streamlit as st
from dotenv import load_dotenv
from markitdown import MarkItDown
from io import BytesIO
import requests
import time
from datetime import datetime
sys.path.append('..')
from utils import render_sidebar, keep_state, get_cosmos_client

from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import (
    MessageRole,
)

# Load environment variables
load_dotenv()

# Initialize MarkItDown for converting files to markdown
md = MarkItDown(enable_plugins=False)

# Create an instance of the AgentsClient using DefaultAzureCredential
agents_client = AgentsClient(
    endpoint=os.getenv("FOUNDRY_API_ENDPOINT"),
    credential=DefaultAzureCredential()
)

class DocumentParser:
    def __init__(self):
        # Create a thread for the agent
        if "thread4" not in st.session_state:
            with st.spinner("Please wait while creating a thread..."):
                st.session_state.thread4 = agents_client.threads.create()

        self.thread = st.session_state.thread4
        
        # Content Understanding API settings
        self.cu_endpoint = os.getenv("CONTENT_UNDERSTANDING_ENDPOINT")
        self.cu_api_key = os.getenv("CONTENT_UNDERSTANDING_API_KEY")
        self.cu_analyzer_id = os.getenv("CONTENT_UNDERSTANDING_ANALYZER_ID")

    def extract_text_from_file(self, file):
        """Extract text from file using MarkItDown"""
        try:
            # Convert the file to markdown format
            md_result = md.convert(file)
            return md_result.text_content
            
        except Exception as e:
            st.error(f"Error reading document: {str(e)}")
            return None

    def parse_with_content_understanding(self, file_data, file_name):
        """Parse document using Azure Content Understanding API"""
        try:
            if not self.cu_endpoint or not self.cu_api_key:
                st.error("Content Understanding API credentials not configured. Please set CONTENT_UNDERSTANDING_ENDPOINT and CONTENT_UNDERSTANDING_API_KEY in your environment variables.")
                return None
                
            # Step 1: Submit document for analysis
            api_url = f"{self.cu_endpoint}/contentunderstanding/analyzers/{self.cu_analyzer_id}:analyze?api-version=2024-12-01-preview"
            
            # Determine content type based on file extension
            file_extension = file_name.lower().split('.')[-1] if file_name else 'pdf'
            content_type_map = {
                'pdf': 'application/pdf',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'md': 'text/markdown'
            }
            content_type = content_type_map.get(file_extension, 'application/pdf')
            
            headers = {
                "Ocp-Apim-Subscription-Key": self.cu_api_key,
                "Content-Type": content_type
            }
            
            # Basic extraction settings
            params = {
                "extractionSettings": {
                    "schemas": [
                        {
                            "name": "DocumentSchema",
                            "fields": [
                                {"name": "Title", "type": "string", "mode": "extract"},
                                {"name": "Summary", "type": "string", "mode": "extract"},
                                {"name": "KeyPoints", "type": "string", "mode": "extract"},
                                {"name": "Entities", "type": "string", "mode": "extract"}
                            ]
                        }
                    ]
                }
            }

            # Send initial request
            response = requests.post(api_url, headers=headers, params=params, data=file_data)

            if response.status_code not in [200, 202]:
                st.error(f"Content Understanding API error: {response.status_code} - {response.text}")
                return None
                
            result = response.json()
            analysis_id = result.get("id")
            
            if not analysis_id:
                st.error("Failed to get analysis ID from Content Understanding API")
                return None
                
            # Step 2: Poll for results
            return self._poll_content_understanding_results(analysis_id)
            
        except Exception as e:
            st.error(f"Error with Content Understanding API: {str(e)}")
            return None
    
    def _poll_content_understanding_results(self, analysis_id, max_attempts=30, delay=2):
        """Poll Content Understanding API for results"""
        try:
            result_url = f"{self.cu_endpoint}/contentunderstanding/analyzers/{self.cu_analyzer_id}/results/{analysis_id}?api-version=2024-12-01-preview"
            
            headers = {
                'Ocp-Apim-Subscription-Key': self.cu_api_key,
                'Content-Type': 'application/json'
            }
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for attempt in range(max_attempts):
                status_text.text(f"Processing document... Attempt {attempt + 1}/{max_attempts}")
                progress_bar.progress((attempt + 1) / max_attempts)
                
                response = requests.get(result_url, headers=headers)
                
                if response.status_code != 200:
                    st.error(f"Error polling results: {response.status_code} - {response.text}")
                    return None
                    
                result = response.json()
                status = result.get("status")
                
                if status == "Succeeded":
                    progress_bar.progress(1.0)
                    status_text.text("Document processing completed!")
                    
                    # Extract markdown content
                    contents = result.get("result", {}).get("contents", [])
                    if contents and len(contents) > 0:
                        markdown_content = contents[0].get("markdown", "")
                        return markdown_content
                    else:
                        st.warning("No content found in the processed document")
                        return None
                        
                elif status == "Failed":
                    st.error("Document processing failed")
                    return None
                elif status == "Running":
                    time.sleep(delay)
                else:
                    st.warning(f"Unknown status: {status}")
                    time.sleep(delay)
                    
            st.error("Timeout waiting for document processing to complete")
            return None
            
        except Exception as e:
            st.error(f"Error polling Content Understanding results: {str(e)}")
            return None

    def process_multiple_documents(self, files_data, use_content_understanding=False):
        """Process multiple documents"""
        results = []
        
        for i, (file_data, file_name) in enumerate(files_data):
            st.write(f"Processing document {i+1}: {file_name}")
            
            if use_content_understanding:
                content = self.parse_with_content_understanding(file_data, file_name)
            else:
                content = self.extract_text_from_file(BytesIO(file_data))
                if content:
                    content = self.parse_document(content)
            
            if content:
                results.append({
                    "file_name": file_name,
                    "content": content,
                    "method": "Content Understanding API" if use_content_understanding else "Traditional Parsing"
                })
            else:
                st.error(f"Failed to process {file_name}")
                
        return results
    
    def parse_document(self, document_text):
        """Parse and structure the document content using AI"""
        try:
            content = f"""
            # Document to Parse:

            <DOCUMENT_CONTENT>
            {document_text}
            </DOCUMENT_CONTENT>

            # Rules:
            - Use original document order.
            - Preserve table row/column order exactly.
            - Merge multiline paragraphs.
            - Omit empty arrays.
            - Do not add fields not specified.
            - Return valid, minified JSON only, no comments, no explanations.
            """

            # Create a message, with the prompt being the message content that is sent to the model
            agents_client.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=content,
            )
            
            # Create and process the run
            run = agents_client.runs.create_and_process(
                thread_id=self.thread.id,
                agent_id=os.getenv("AGENT_DOCUMENT_PARSER_ID"),
            )

            if run.status == "failed":
                raise Exception(run.last_error)

            # Get the last message from the agent
            last_msg = agents_client.messages.get_last_message_text_by_role(
                thread_id=self.thread.id, role=MessageRole.AGENT
            )
 
            return last_msg.text.value

        except Exception as e:
            st.error(f"Error parsing document: {str(e)}")
            return None

    def save_to_cosmosdb(self, parsed_content, file_name):
        """Save parsed document content to CosmosDB"""
        try:
            # Get CosmosDB container client for 'scoping' container
            container_client = get_cosmos_client('scoping')
            if not container_client:
                st.error("Failed to connect to CosmosDB")
                return False
            
            # Parse the JSON content to extract sections
            try:
                parsed_json = json.loads(parsed_content)
                sections = parsed_json.get('sections', [])
            except json.JSONDecodeError:
                st.error("Invalid JSON format in parsed content")
                return False
            
            if not sections:
                st.warning("No sections found in parsed content")
                return False
            
            # Prepare the document to save
            document = {
                "id": f"doc_{int(datetime.now().timestamp())}_{hash(file_name) % 10000}",
                "file_name": file_name,
                "sections": sections,
                "timestamp": datetime.now().isoformat()
            }
            
            # Save to CosmosDB
            container_client.create_item(document)
            st.success(f"✅ Document saved to CosmosDB with ID: {document['id']}")
            return True
            
        except Exception as e:
            st.error(f"Error saving to CosmosDB: {str(e)}")
            return False

def main():
    # Render shared sidebar navigation
    render_sidebar()
    
    st.title("📋 Unstructured Document Parser")
    st.markdown("Extract and structure content from unstructured documents including PDFs, Word documents, and Markdown files.")
    
    # Initialize parser
    parser = DocumentParser()
    container1 = st.container(border=True, key="container1")
    
    # File upload section
    container1.subheader("📁 Upload Document")

    uploaded_file = container1.file_uploader(
        "Upload Document to Parse",
        type=["pdf", "docx", "md"],
        key="document_to_parse",
        help="Upload a PDF, Word document, or Markdown file to extract and structure its content"
    )

    # Add checkbox for Content Understanding feature
    use_content_understanding = container1.checkbox(
        "Use Content Understanding",
        value=False,
        key="use_content_understanding",
        help="Enable advanced content understanding for better document analysis and structure extraction"
    )

    # Add checkbox for saving to CosmosDB
    save_to_cosmosdb = container1.checkbox(
        "Save to CosmosDB",
        value=False,
        key="save_to_cosmosdb",
        help="Save the parsed document content to Azure Cosmos DB for future reference and analysis"
    )

    # Read the file content once
    upload_content = uploaded_file.read() if uploaded_file else None
    parsed_content = None

    # Keep the state of the uploaded file
    if keep_state(upload_content, "upload_content_parser"):
        upload_content = st.session_state.upload_content_parser

    if keep_state(uploaded_file, "uploaded_file_parser"):
        uploaded_file = st.session_state.uploaded_file_parser
        container1.success(f"✅ Uploaded file: {uploaded_file.name}")

    # Show example or help
    with container1.expander("ℹ️ How this tool works?"):
        st.markdown("""
        ### How to Use the Document Parser:
        
        1. **Upload Document**: Upload a .pdf, .docx, or .md file containing unstructured content
        2. **Choose Processing Method**: 
           - **Standard Parsing**: Uses MarkItDown + AI agent for content extraction
           - **Content Understanding**: Uses Azure Content Understanding API for advanced analysis
        3. **Enable Save to CosmosDB** (Optional): Check to automatically save parsed results to Azure Cosmos DB
        4. **Click 'Parse Document'**: The AI will extract and organize the document content
        
        ### What You'll Get:
        - **Document Analysis**: Understanding of document type and purpose
        - **Structured Content**: Key sections and headings organized clearly
        - **Data Extraction**: Important data points, dates, names, and entities
        - **Content Summary**: Overview of the main document content
        - **Organized Information**: Tables, lists, and structured data presented clearly
        
        ### CosmosDB Integration:
        - **Automatic Save**: When enabled, parsed content is automatically saved to CosmosDB
        - **Manual Save**: Use the "💾 Save to CosmosDB" button to save existing parsed content
        - **Storage Format**: Saves the "sections" field from JSON output with timestamp and metadata
        - **Container**: Uses the 'scoping' container as specified in the requirements
        
        ### Processing Methods:
        - **Standard Parsing**: Traditional text extraction using MarkItDown + AI structuring
        - **Content Understanding**: Advanced Azure API text extraction + AI structuring
        
        Both methods use the same AI agent for final document structuring and return JSON format.
        
        ### Supported Formats:
        - PDF documents (.pdf) - Extracts text from PDF files
        - Microsoft Word documents (.docx) - Parses Word document content
        - Markdown files (.md) - Processes Markdown formatted text
        
        ### Environment Variables (for Content Understanding):
        - `CONTENT_UNDERSTANDING_ENDPOINT`: Your Azure Content Understanding endpoint
        - `CONTENT_UNDERSTANDING_API_KEY`: Your Azure Content Understanding API key
        - `CONTENT_UNDERSTANDING_ANALYZER_ID`: Analyzer ID (optional, defaults to 'xcash_business_reg')
        
        ### CosmosDB Environment Variables:
        - `AZURE_COSMOS_ENDPOINT`: Your Azure Cosmos DB endpoint
        - `AZURE_COSMOS_DATABASE`: Database name (e.g., 'pmo-agent-db')
        - `AZURE_COSMOS_KEY`: Your Cosmos DB key (or use managed identity)
        
        ### Use Cases:
        - Extract key information from reports
        - Structure unorganized documents
        - Parse meeting notes and minutes
        - Analyze contracts and agreements
        - Extract data from research papers
        - Store parsed content for future analysis and retrieval
        """)

    # Parse button
    if st.button("🔍 Parse Document", type="primary", disabled=not uploaded_file):
        document_text = None
        
        if use_content_understanding:
            with st.spinner("Processing document with Content Understanding API..."):
                # Use Content Understanding API to get document text
                document_text = parser.parse_with_content_understanding(upload_content, uploaded_file.name)
                if not document_text:
                    st.error("❌ Failed to process document with Content Understanding API.")
        else:
            with st.spinner("Extracting text from document..."):
                # Extract text from the document using MarkItDown
                document_text = parser.extract_text_from_file(BytesIO(upload_content))
                if not document_text:
                    st.error("❌ Failed to extract text from the document.")

        # Keep the state of document_text
        if keep_state(document_text, "document_text"):
            document_text = st.session_state.document_text

        # Parse the document using AI agent (common for both methods)
        if document_text:
            with st.spinner("Parsing and structuring document content with AI..."):
                parsed_content = parser.parse_document(document_text)
                if parsed_content:
                    st.success("✅ Document processed successfully!")
                else:
                    st.error("❌ Failed to parse document with AI agent.")
                    
            # Save to CosmosDB if checkbox is enabled
            if save_to_cosmosdb and parsed_content:
                with st.spinner("Saving to CosmosDB..."):
                    parser.save_to_cosmosdb(parsed_content, uploaded_file.name)

    # Keep the state of parsed content
    if keep_state(parsed_content, "parsed_content"):
        parsed_content = st.session_state.parsed_content

    # Keep the state of document_text (also check outside the button click)
    if keep_state(None, "document_text"):
        document_text = st.session_state.document_text

    if parsed_content:
        st.subheader("📊 Parsed Document Content")
        
        # Display the parsed content in an expandable format
        with st.expander("📋 Structured Content", expanded=True):
            try:
                # Display as JSON for both methods
                st.write(json.loads(parsed_content))
            except json.JSONDecodeError:
                # Fallback to text display if JSON parsing fails
                st.text(parsed_content)
        
        # Additional features
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Download parsed content as text
            st.download_button(
                label="📄 Download as Text",
                data=parsed_content,
                file_name=f"parsed_{uploaded_file.name if uploaded_file else 'document'}.txt",
                mime="text/plain"
            )
        
        with col2:
            # Download as markdown
            st.download_button(
                label="📝 Download as Markdown",
                data=parsed_content,
                file_name=f"parsed_{uploaded_file.name if uploaded_file else 'document'}.md",
                mime="text/markdown"
            )
        
        with col3:
            # Save to CosmosDB button (if not already saved during parsing)
            if st.button("💾 Save to CosmosDB", key="save_existing_to_cosmos"):
                if uploaded_file:
                    with st.spinner("Saving to CosmosDB..."):
                        parser.save_to_cosmosdb(parsed_content, uploaded_file.name)
                else:
                    st.error("No file information available for saving to CosmosDB")

        # Summary metrics section
        col1, col2 = st.columns(2)
        with col1:
            # Create summary metrics
            word_count = len(parsed_content.split())
            st.metric("Content Length", f"{word_count} words")
        
        with col2:
            try:
                # Count sections if JSON format
                parsed_json = json.loads(parsed_content)
                sections_count = len(parsed_json.get('sections', []))
                st.metric("Sections Found", sections_count)
            except json.JSONDecodeError:
                st.metric("Format", "Plain Text")

        # Raw extracted text section (optional)
        with st.expander("🔍 View Raw Extracted Text"):
            if document_text:
                st.text_area(
                    "Raw extracted text:",
                    document_text,
                    height=200,
                    disabled=True
                )
                
                # Character and word count for raw text
                raw_word_count = len(document_text.split())
                raw_char_count = len(document_text)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Raw Text Words", raw_word_count)
                with col2:
                    st.metric("Raw Text Characters", raw_char_count)
            else:
                st.info("No raw text available. Process a document first to see the extracted text.")

if __name__ == "__main__":
    main()
