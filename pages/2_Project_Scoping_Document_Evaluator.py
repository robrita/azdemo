# pages/2_Project_Scoping_Document_Evaluator.py
import os
import sys
import streamlit as st
from dotenv import load_dotenv
from markitdown import MarkItDown
from io import BytesIO
sys.path.append('..')
from utils import render_sidebar, keep_state

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

class DocumentEvaluator:
    def __init__(self):
        # Create a thread for the agent
        if "thread2" not in st.session_state:
            with st.spinner("Please wait while creating a thread..."):
                st.session_state.thread2 = agents_client.threads.create()

        self.thread = st.session_state.thread2

    def extract_text_from_file(self, file):
        """Extract text from file"""
        try:
            # Convert the file to markdown format
            md_result = md.convert(file)

            return md_result.text_content
            
        except Exception as e:
            st.error(f"Error reading document: {str(e)}")
            return None
    
    def evaluate_document(self, scoping_doc_text, guidelines_text):
        """Evaluate scoping document against guidelines"""
        try:
            content = f"""
            # Guidelines and Scoping documents:

            <GUIDELINES DOCUMENT>
            {guidelines_text}
            </GUIDELINES DOCUMENT>

            <SCOPING DOCUMENT>
            {scoping_doc_text}
            </SCOPING DOCUMENT>

            # Output format:
            Format your response in clear sections with headers and bullet points.
            """

            # Create a message, with the prompt being the message content that is sent to the model
            agents_client.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=content,
            )
            
            # [START create_and_process]
            run = agents_client.runs.create_and_process(
                thread_id=self.thread.id,
                agent_id=os.getenv("AGENT_DOCUMENT_EVALUATOR_ID"),
            )

            # [END create_and_process]
            if run.status == "failed":
                raise Exception(run.last_error)

            # Get the last message from the sender
            last_msg = agents_client.messages.get_last_message_text_by_role(
                thread_id=self.thread.id, role=MessageRole.AGENT
            )
 
            return last_msg.text.value

        except Exception as e:
            st.error(f"Error evaluating document: {str(e)}")
            return None

def main():
    # Render shared sidebar navigation
    render_sidebar()
    
    st.title("📄 Project Scoping Document Evaluator")
    st.markdown("Analyze project scoping documents against guidelines to identify gaps and improvements.")
    
    # Initialize evaluator
    evaluator = DocumentEvaluator()
    container1 = st.container(border=True, key="container1")
    
    # File upload section
    container1.subheader("📁 Upload Document")

    scoping_file = container1.file_uploader(
        "Upload Project Scoping Document",
        type=["pdf", "docx", "md"],
        key="scoping_doc",
        help="Upload the project scoping document to be evaluated"
    )

    # Read the file content once
    upload_content = scoping_file.read() if scoping_file else None
    evaluation = None

    # Keep the state of the uploaded file
    if keep_state(upload_content, "upload_content"):
        upload_content = st.session_state.upload_content

    if keep_state(scoping_file, "scoping_file"):
        scoping_file = st.session_state.scoping_file
        container1.success(f"✅ Uploaded file: {scoping_file.name}")

    # Show example or help
    with container1.expander("ℹ️ How this tool works?"):
        st.markdown("""
        ### How to Use the Document Evaluator:
        
        1. **Upload Project Scoping Document**: Upload the .docx, .pdf, or .md file containing your project scope
        2. **Click 'Analyze Document'**: The AI will compare the uploaded document against the known scoping guidelines and provide a detailed evaluation
        
        ### What You'll Get:
        - **Missing Sections**: Identify what's missing from your scoping document
        - **Incomplete Details**: Find areas that need more information
        - **Misalignments**: Spot content that doesn't follow guidelines
        - **Recommendations**: Get specific suggestions for improvement
        - **Overall Score**: Receive a completeness rating
        
        ### Supported Formats:
        - Microsoft Word documents (.docx)
        - PDF documents (.pdf)
        - Markdown files (.md)
        """)

    # Analyze button
    if st.button("🔍 Analyze Document", type="primary", disabled=not scoping_file):
        with st.spinner("Extracting text from documents..."):
            # Extract text from both documents
            scoping_text = evaluator.extract_text_from_file(BytesIO(upload_content))
            guidelines_text = evaluator.extract_text_from_file("./data/project_scoping_guidelines.md")

        if scoping_text and guidelines_text:
            with st.spinner("Analyzing document compliance..."):
                # Evaluate the document
                evaluation = evaluator.evaluate_document(scoping_text, guidelines_text)
                st.success("✅ Documents processed successfully!")

        else:
            st.error("❌ Failed to extract text from one or both documents.")

    if keep_state(evaluation, "evaluation"):
        evaluation = st.session_state.evaluation

    if evaluation:
        st.subheader("📊 Evaluation Report")
        
        # Display the evaluation in an expandable format
        with st.expander("📋 Full Evaluation Report", expanded=True):
            st.markdown(evaluation)
        
        # Download option
        col1, col2 = st.columns(2)
        
        with col1:
            # Download evaluation as text
            st.download_button(
                label="📄 Download Report as Text",
                data=evaluation,
                file_name="evaluation_report.txt",
                mime="text/plain"
            )
        
        with col2:
            # Create summary metrics
            word_count = len(evaluation.split())
            st.metric("Report Length", f"{word_count} words")
            

if __name__ == "__main__":
    main()