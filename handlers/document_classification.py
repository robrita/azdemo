import logging
import os
import sys
from typing import Any

sys.path.append("..")
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential

# Configure logging
logger = logging.getLogger(__name__)


class DocumentClassification:
    """
    Handler for Azure Document Intelligence - Document Classification
    Uses custom classification models to identify document types
    """

    def __init__(self, service_name=None):
        self.service_name = service_name or "Document Classification"
        # Initialize Azure Document Intelligence client
        self.endpoint = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        self.key = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        self.model_id = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_CLASSIFICATION_MODEL")

        # Initialize client if credentials are available
        self.client = None
        if self.endpoint and self.key:
            self.client = DocumentIntelligenceClient(
                endpoint=self.endpoint, credential=AzureKeyCredential(self.key)
            )
        else:
            logger.error(f"Missing Document Intelligence credentials for {self.service_name}")

    def classify(self, uploaded_file) -> dict[str, Any]:
        """
        Classify document type using Document Intelligence Classification service

        Args:
            uploaded_file: Streamlit uploaded file object

        Returns:
            Dict containing classification results with docType, confidence, and processing info
        """
        import time

        logger.info(f"Document Classification started: {uploaded_file.name}")
        try:
            # Start timing
            start_time = time.time()

            # Read file content
            file_bytes = uploaded_file.getvalue()
            file_name = uploaded_file.name
            file_type = uploaded_file.type

            # Validate model_id is configured
            if not self.model_id:
                raise ValueError(
                    "AZURE_DOCUMENT_INTELLIGENCE_CLASSIFICATION_MODEL environment variable not set"
                )

            # Begin classify document operation
            logger.debug(f"Classifying document with model '{self.model_id}'...")
            poller = self.client.begin_classify_document(
                self.model_id, AnalyzeDocumentRequest(bytes_source=file_bytes)
            )
            result = poller.result()

            # Calculate processing time
            processing_time = time.time() - start_time

            # Extract classification data from result
            classification_data = {
                "service": self.service_name,
                "file_info": {"name": file_name, "type": file_type, "size": len(file_bytes)},
                "model_info": {
                    "model_id": result.model_id,
                    "api_version": getattr(result, "api_version", "N/A"),
                },
                "documents": [],
            }

            # Process classified documents
            if result.documents:
                for idx, document in enumerate(result.documents):
                    doc_data = {
                        "document_number": idx + 1,
                        "doc_type": document.doc_type,
                        "confidence": document.confidence,
                    }
                    classification_data["documents"].append(doc_data)

                    logger.info(
                        f"Document #{idx + 1} classified as: {document.doc_type} "
                        f"(confidence: {document.confidence:.3f})"
                    )

            # Add processing summary
            classification_data["processing_info"] = {
                "pages_processed": len(result.pages) if result.pages else 0,
                "documents_found": len(result.documents) if result.documents else 0,
                "processing_time_seconds": round(processing_time, 3),
            }

            # Extract docType from first document (primary use case)
            if result.documents and len(result.documents) > 0:
                doc_type = result.documents[0].doc_type
                confidence = result.documents[0].confidence

                # Set to "unknown" if:
                # 1. doc_type contains the word "null"
                # 2. doc_type doesn't have "null" but confidence is less than 0.2
                if "null" in doc_type.lower() or confidence < 0.2:
                    classification_data["docType"] = "unknown"
                    classification_data["confidence"] = confidence
                else:
                    classification_data["docType"] = doc_type
                    classification_data["confidence"] = confidence
            else:
                classification_data["docType"] = "unknown"
                classification_data["confidence"] = 0.0

            logger.info(
                f"Classification completed: {file_name} | "
                f"Type: {classification_data['docType']} | "
                f"Time: {processing_time:.3f}s"
            )

            return classification_data

        except Exception as e:
            import traceback

            logger.error(
                f"Classification error: {file_name if 'file_name' in locals() else 'unknown'} | "
                f"{self.service_name} | {str(e)}",
                exc_info=True,
            )
            return {
                "service": self.service_name,
                "error": f"Classification failed: {str(e)}",
                "error_details": traceback.format_exc(),
                "file_info": {
                    "name": uploaded_file.name if uploaded_file else "Unknown",
                    "type": uploaded_file.type if uploaded_file else "Unknown",
                },
                "docType": "unknown",
                "confidence": 0.0,
            }
