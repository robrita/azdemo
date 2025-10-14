# handlers/__init__.py
"""
Document Extraction Handlers Package

This package contains handler classes for various document extraction services:
- DocumentIntelligenceTemplate: Azure Document Intelligence with template-based extraction
- DocumentIntelligenceNeural: Azure Document Intelligence with neural models
- ContentUnderstanding: Semantic content analysis and understanding
- MistralDocumentAI: Mistral's AI-powered document extraction
- GPT5ForVision: OpenAI GPT-5 with vision capabilities
- GPT41ForVision: OpenAI GPT-4.1 with vision capabilities

Each handler implements an extract() method that takes an uploaded file and returns
structured extraction results.
"""

from .document_intelligence import DocumentIntelligence
from .content_understanding import ContentUnderstanding
from .mistral_document_ai import MistralDocumentAI
from .gpt5_vision import GPT5ForVision
from .gpt41_vision import GPT41ForVision

__all__ = [
    'DocumentIntelligence',
    'DocumentIntelligenceNeural', 
    'ContentUnderstanding',
    'MistralDocumentAI',
    'GPT5ForVision',
    'GPT41ForVision'
]