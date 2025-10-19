import base64
import io
import logging
import os
import sys
import time
from typing import Any

import fitz  # PyMuPDF
from openai import AzureOpenAI
from PIL import Image

sys.path.append("..")
from schemas.gpt_schema import DocSchema
from utils import save_extraction_to_json

# Configure logging
logger = logging.getLogger(__name__)


class GPTForVision:
    """
    Handler for GPT for Vision service
    Uses OpenAI's GPT model with vision capabilities for document analysis
    """

    def __init__(self, service_name=None):
        self.service_name = service_name

        # Initialize Azure OpenAI configuration
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.deployment_gpt41 = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT4-1")
        self.deployment_gpt5 = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT5")
        self.subscription_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.api_version = "2025-01-01-preview"

        # Initialize Azure OpenAI client with key-based authentication
        self.client = None
        if self.endpoint and self.subscription_key:
            try:
                self.client = AzureOpenAI(
                    azure_endpoint=self.endpoint,
                    api_key=self.subscription_key,
                    api_version=self.api_version,
                )
            except Exception as e:
                logger.error(f"GPT Vision init error: {service_name} | {str(e)}", exc_info=True)
                logger.warning(f"Failed to initialize Azure OpenAI client: {str(e)}")
        else:
            logger.error(f"Missing GPT Vision credentials for {service_name}")

    def _convert_pdf_to_images(self, file_bytes: bytes) -> list:
        """
        Convert PDF bytes to list of PIL images using PyMuPDF

        Args:
            file_bytes: PDF file content as bytes

        Returns:
            List of PIL Image objects
        """
        try:
            # Open PDF from bytes
            pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
            images = []

            # Convert each page to image
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]

                # Render page to pixmap at 200 DPI (matrix zoom factor ~2.78)
                zoom = 200 / 72  # 72 DPI is default
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)

                # Convert pixmap to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)

            pdf_document.close()
            return images

        except Exception as e:
            logger.error(f"PDF conversion error | {str(e)}", exc_info=True)
            return []

    def _image_to_base64(self, image) -> str:
        """
        Convert PIL Image to base64 string

        Args:
            image: PIL Image object

        Returns:
            Base64 encoded string
        """
        byte_io = io.BytesIO()
        image.save(byte_io, format="PNG")
        base64_data = base64.b64encode(byte_io.getvalue()).decode("utf-8")
        return base64_data

    def extract(self, uploaded_file) -> dict[str, Any]:
        """
        Extract data using GPT for Vision service with Azure OpenAI SDK

        Args:
            uploaded_file: Streamlit uploaded file object

        Returns:
            Dict containing extracted data
        """
        logger.info(f"GPT for Vision extraction started: {uploaded_file.name}")
        try:
            # Start timing
            start_time = time.time()

            # Check if client is initialized
            if not self.client:
                return {
                    "service": self.service_name,
                    "error": "Azure OpenAI client not initialized. Please check credentials.",
                    "file_info": {"name": uploaded_file.name, "type": uploaded_file.type},
                }

            # Read file content
            file_bytes = uploaded_file.getvalue()
            file_name = uploaded_file.name
            file_type = uploaded_file.type

            # Check file type and convert PDF to images if necessary
            images_to_process = []
            pages_count = 1

            if "pdf" in file_type.lower():
                logger.debug("Converting PDF to images...")
                images = self._convert_pdf_to_images(file_bytes)
                if not images:
                    return {
                        "service": self.service_name,
                        "error": "Failed to convert PDF to images",
                        "file_info": {"name": file_name, "type": file_type},
                    }
                images_to_process = images
                pages_count = len(images)
            else:
                # For image files, use directly
                image = Image.open(io.BytesIO(file_bytes))
                images_to_process = [image]
                pages_count = 1

            # Prepare the prompts and content
            system_prompt = "You are an AI assistant that extracts data from the given documents."

            user_text_prompt = """Extract the data from this document.
- If a value is not present, provide null.
- Dates should be in the format MM/DD/YYYY.
- Extract TIN in format XXX-XXX-XXX-XXXXX or variations."""

            # Process first page/image
            base64_image = self._image_to_base64(images_to_process[0])

            user_content = [
                {"type": "text", "text": user_text_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                },
            ]

            chat_prompt = [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {"role": "user", "content": user_content},
            ]

            # deployment is deployment_gpt5 if service_name contains the word 'GPT-5' else deployment_gpt41
            self.deployment = (
                self.deployment_gpt5
                if self.service_name and "gpt-5" in self.service_name.lower()
                else self.deployment_gpt41
            )

            # temperature is 1 for GPT-5 and 0 for GPT-4-1
            temperature = 1 if self.deployment == self.deployment_gpt5 else 0

            # Send request to Azure OpenAI SDK
            logger.debug(f"Analyzing document with Azure OpenAI {self.deployment} Vision...")
            completion = self.client.beta.chat.completions.parse(
                model=self.deployment,
                messages=chat_prompt,
                response_format=DocSchema,
                temperature=temperature,
                top_p=1,
            )

            # Calculate processing time
            processing_time = time.time() - start_time

            # Extract and save data
            parsed_data = completion.choices[0].message.parsed

            # Set overall confidence to 0.0 (GPT doesn't provide per-field confidence)
            overall_confidence = 0.0

            # Build extracted data structure
            extracted_data = {
                "service": self.service_name,
                "file_info": {"name": file_name, "type": file_type, "size": len(file_bytes)},
                "model_info": {"model_id": self.deployment, "api_version": self.api_version},
                "documents": [],
            }

            # Process extracted fields
            if parsed_data:
                doc_data = {
                    "document_number": 1,
                    "doc_type": "BIR Tax Document",
                    "confidence": overall_confidence,
                    "fields": {},
                }

                # Extract fields - convert Pydantic model to dict
                parsed_dict = parsed_data.model_dump()

                # Build fields dictionary for save_extraction_to_json
                # Following the same pattern as Mistral Document AI handler
                fields_dict = {}

                # Map the extracted properties to fields with confidence scores
                for field_name, field_value in parsed_dict.items():
                    if field_value:  # Only include fields with values
                        fields_dict[field_name] = {
                            "content": str(field_value),
                            "confidence": 0.0,
                            "type": "string",
                        }

                # Add fields to document data for display
                for field_name, field_info in fields_dict.items():
                    doc_data["fields"][field_name] = {
                        "type": field_info["type"],
                        "content": field_info["content"],
                        "confidence": field_info["confidence"],
                    }

                extracted_data["documents"].append(doc_data)

                # Save results to JSON file using common utility function
                if fields_dict:
                    save_extraction_to_json(
                        file_name,
                        self.service_name,
                        pages_count=pages_count,
                        fields=fields_dict,
                        overall_confidence=overall_confidence,
                        processing_time=processing_time,
                    )

            # Add processing summary
            extracted_data["processing_info"] = {
                "pages_processed": pages_count,
                "documents_found": len(extracted_data["documents"]),
                "processing_time_seconds": round(processing_time, 3),
            }

            return extracted_data

        except Exception as e:
            import traceback

            logger.error(
                f"GPT Vision error: {uploaded_file.name if 'uploaded_file' in locals() else 'unknown'} "
                f"| {self.service_name} | {str(e)}",
                exc_info=True,
            )
            return {
                "service": self.service_name,
                "error": f"GPT Vision extraction failed: {str(e)}",
                "error_details": traceback.format_exc(),
                "file_info": {
                    "name": uploaded_file.name if uploaded_file else "Unknown",
                    "type": uploaded_file.type if uploaded_file else "Unknown",
                },
            }
