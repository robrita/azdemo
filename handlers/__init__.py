# handlers/__init__.py
"""
Document Extraction Handlers Package

This package contains handler classes for various document extraction services:
- DocumentIntelligenceTemplate: Azure Document Intelligence with template-based extraction
- DocumentIntelligenceNeural: Azure Document Intelligence with neural models
- ContentUnderstanding: Semantic content analysis and understanding
- MistralDocumentAI: Mistral's AI-powered document extraction
- GPTForVision: OpenAI GPT with vision capabilities

Each handler implements an extract() method that takes an uploaded file and returns
structured extraction results.
"""

from .content_understanding import ContentUnderstanding
from .document_intelligence import DocumentIntelligence
from .gpt_vision import GPTForVision
from .mistral_document_ai import MistralDocumentAI

__all__ = [
    "DocumentIntelligence",
    "DocumentIntelligenceNeural",
    "ContentUnderstanding",
    "MistralDocumentAI",
    "GPTForVision",
]
