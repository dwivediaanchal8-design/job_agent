"""
services/resume_parser.py — AI Resume Parser (Stub for Phase 3)
================================================================
Parses PDF and DOCX resumes into structured JSON using GPT-4o.
This stub is created now so the resume upload route doesn't break.
Full AI implementation happens in Phase 3.
"""

from loguru import logger


class ResumeParser:
    """
    Parses uploaded resume files into structured data.
    Phase 1: Returns raw text only.
    Phase 3: Adds GPT-4o structured extraction.
    """

    async def parse(self, file_path: str, file_type: str) -> tuple[str, dict]:
        """
        Parse a resume file.

        Args:
            file_path: Absolute path to the file.
            file_type: 'pdf' or 'docx'

        Returns:
            (raw_text, parsed_json) tuple
        """
        raw_text = self._extract_text(file_path, file_type)
        # Phase 3 will call GPT-4o here
        parsed_json = {"raw": True, "text_preview": raw_text[:200]}
        return raw_text, parsed_json

    def _extract_text(self, file_path: str, file_type: str) -> str:
        """Extract plain text from PDF or DOCX."""
        if file_type == "pdf":
            return self._extract_pdf(file_path)
        elif file_type == "docx":
            return self._extract_docx(file_path)
        return ""

    def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF using PyMuPDF."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            logger.info(f"📄 Extracted {len(text)} chars from PDF")
            return text
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return ""

    def _extract_docx(self, file_path: str) -> str:
        """Extract text from DOCX using python-docx."""
        try:
            from docx import Document
            doc = Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            logger.info(f"📄 Extracted {len(text)} chars from DOCX")
            return text
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}")
            return ""
