import streamlit as st
from typing import Any, Dict
import io
import os
import sys
sys.path.append('..')
from utils import save_extraction_to_json
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

class DocumentIntelligence:
    """
    Handler for Azure Document Intelligence - Template-based extraction
    Uses predefined templates for structured document types
    """
    
    def __init__(self, service_name=None):
        self.service_name = service_name
        # Initialize Azure Document Intelligence client
        self.endpoint = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        self.key = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        self.model_template = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_TEMPLATE_MODEL")
        self.model_neural = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_NEURAL_MODEL")

        # Initialize client if credentials are available
        self.client = None
        if self.endpoint and self.key:
            self.client = DocumentIntelligenceClient(
                endpoint=self.endpoint, 
                credential=AzureKeyCredential(self.key)
            )
        
    def extract(self, uploaded_file) -> Dict[str, Any]:
        """
        Extract data using Document Intelligence Template service
        
        Args:
            uploaded_file: Streamlit uploaded file object
            
        Returns:
            Dict containing extracted data
        """
        import time
        
        try:
            # Start timing
            start_time = time.time()
            
            # Read file content
            file_bytes = uploaded_file.getvalue()
            file_name = uploaded_file.name
            file_type = uploaded_file.type

            # model_id is template if service_name contains the word 'Template', else neural
            model_id = self.model_template if self.service_name and 'template' in self.service_name.lower() else self.model_neural

            # Begin analyze document operation
            with st.spinner(f"Analyzing document with model '{model_id}'..."):
                poller = self.client.begin_analyze_document(
                    model_id, AnalyzeDocumentRequest(bytes_source=file_bytes)
                )
                result = poller.result()
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Extract data from result
            extracted_data = {
                "service": self.service_name,
                "file_info": {
                    "name": file_name,
                    "type": file_type,
                    "size": len(file_bytes)
                },
                "model_info": {
                    "model_id": result.model_id,
                    "api_version": getattr(result, 'api_version', 'N/A')
                },
                "documents": []
            }
            
            # Process documents
            if result.documents:
                for idx, document in enumerate(result.documents):
                    doc_data = {
                        "document_number": idx + 1,
                        "doc_type": document.doc_type,
                        "confidence": document.confidence,
                        "fields": {}
                    }
                    
                    # Extract fields
                    for name, field in document.fields.items():
                        doc_data["fields"][name] = {
                            "type": field.type if hasattr(field, 'type') else 'unknown',
                            "content": field.content if hasattr(field, 'content') else str(field.value) if hasattr(field, 'value') else 'N/A',
                            "confidence": field.confidence if hasattr(field, 'confidence') else 0.0
                        }
                    
                    extracted_data["documents"].append(doc_data)
            
            # Add processing summary
            extracted_data["processing_info"] = {
                "pages_processed": len(result.pages) if result.pages else 0,
                "documents_found": len(result.documents) if result.documents else 0,
                "tables_found": len(result.tables) if result.tables else 0
            }
            
            # Save results to JSON file using common utility function
            if result.documents and len(result.documents) > 0:
                # Use the first document's fields for scoring
                first_doc = result.documents[0]
                pages_count = len(result.pages) if result.pages else 0
                # Pass document.confidence as overall_confidence and processing time
                save_extraction_to_json(
                    file_name, 
                    self.service_name, 
                    pages_count, 
                    first_doc.fields, 
                    overall_confidence=first_doc.confidence,
                    processing_time=processing_time
                )
            
            return extracted_data
            
        except Exception as e:
            import traceback
            return {
                "service": self.service_name,
                "error": f"Template extraction failed: {str(e)}",
                "error_details": traceback.format_exc(),
                "file_info": {
                    "name": uploaded_file.name if uploaded_file else "Unknown",
                    "type": uploaded_file.type if uploaded_file else "Unknown"
                }
            }