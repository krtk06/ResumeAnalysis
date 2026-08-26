import io
import re

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    from docx import Document
except ImportError:
    Document = None

class ResumeParser:
    @staticmethod
    def extract_text_from_pdf(file_bytes: bytes) -> str:
        if PyPDF2 is None:
            raise ImportError("PyPDF2 not installed")
        
        pdf_file = io.BytesIO(file_bytes)
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    
    @staticmethod
    def extract_text_from_docx(file_bytes: bytes) -> str:
        if Document is None:
            raise ImportError("python-docx not installed")
        
        doc_file = io.BytesIO(file_bytes)
        doc = Document(doc_file)
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text
    
    @staticmethod
    def parse(file_bytes: bytes, filename: str) -> str:
        ext = filename.lower().split('.')[-1]
        
        if ext == 'pdf':
            return ResumeParser.extract_text_from_pdf(file_bytes)
        elif ext in ['doc', 'docx']:
            return ResumeParser.extract_text_from_docx(file_bytes)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
    
    @staticmethod
    def clean_text(text: str) -> str:
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text