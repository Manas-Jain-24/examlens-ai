"""Local PDF extraction with bounded, optional command-line OCR."""
from dataclasses import dataclass, field
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from pypdf import PdfReader
from backend.core.config import settings

@dataclass
class PdfExtraction:
    text: str
    warnings: list[str] = field(default_factory=list)
    pages: list[dict] = field(default_factory=list)

def ocr_status():
    renderer, engine = shutil.which(settings.PDF_RENDERER_CMD), shutil.which(settings.TESSERACT_CMD)
    return {'enabled': settings.OCR_ENABLED, 'available': bool(renderer and engine),
            'renderer_available': bool(renderer), 'tesseract_available': bool(engine),
            'language': settings.OCR_LANGUAGE, 'maximum_pages': settings.MAX_PDF_PAGES,
            'document_timeout_seconds': settings.OCR_TIMEOUT_SECONDS}

def _remaining(deadline):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise ValueError('OCR exceeded the document time limit. Split the PDF or paste corrected text.')
    return seconds

def _ocr_page(pdf_bytes, number, deadline):
    renderer, engine = shutil.which(settings.PDF_RENDERER_CMD), shutil.which(settings.TESSERACT_CMD)
    if not renderer or not engine:
        raise ValueError('OCR requires local Tesseract and Poppler (pdftoppm). Install/configure both, or paste extracted text.')
    with tempfile.TemporaryDirectory(prefix='examlens-ocr-') as folder:
        source = Path(folder) / 'source.pdf'
        source.write_bytes(pdf_bytes)
        prefix = Path(folder) / 'page'
        try:
            subprocess.run([renderer, '-f', str(number), '-l', str(number), '-scale-to', '2400',
                            '-singlefile', '-png', str(source), str(prefix)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                           timeout=_remaining(deadline), shell=False)
            result = subprocess.run([engine, str(prefix) + '.png', 'stdout', '-l', settings.OCR_LANGUAGE, '--psm', '3'],
                                    check=True, capture_output=True, timeout=_remaining(deadline), shell=False)
            return result.stdout.decode('utf-8', errors='replace').strip()
        except subprocess.TimeoutExpired:
            raise ValueError('OCR exceeded the document time limit. Split the PDF or paste corrected text.')
        except (subprocess.CalledProcessError, OSError):
            raise ValueError('Local OCR failed. Verify Tesseract, Poppler, and the configured language data.')

def extract_pdf_document(pdf_bytes):
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if reader.is_encrypted:
            raise ValueError('Password-protected PDFs are not supported. Upload an unlocked copy.')
        if len(reader.pages) > settings.MAX_PDF_PAGES:
            raise ValueError(f'PDF exceeds the {settings.MAX_PDF_PAGES}-page limit. Split it before uploading.')
        output, warnings, pages = [], [], []
        deadline = time.monotonic() + settings.OCR_TIMEOUT_SECONDS
        for number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ''
            method = 'native'
            if sum(char.isalnum() for char in text) < 20:
                if settings.OCR_ENABLED:
                    recognized = _ocr_page(pdf_bytes, number, deadline)
                    if len(recognized.strip()) > len(text.strip()):
                        text, method = recognized, 'ocr'
                    warnings.append(f'Page {number}: local OCR attempted; verify the extracted wording and marks.')
                else:
                    warnings.append(f'Page {number}: little or no selectable text. OCR is disabled; enable local OCR or paste corrected text.')
                if not text.strip():
                    warnings.append(f'Page {number}: no readable text; manually add any missing content.')
            output.append(text)
            pages.append({'page': number, 'method': method, 'characters': len(text.strip())})
        extracted = '\n'.join(output).strip()
        if not extracted:
            raise ValueError('No readable PDF text. Enable OCR_ENABLED with local Tesseract and Poppler, or paste extracted text.')
        return PdfExtraction(extracted, warnings, pages)
    except ValueError:
        raise
    except Exception:
        raise ValueError('Could not read this PDF. Upload a valid, unlocked PDF or paste text.')
