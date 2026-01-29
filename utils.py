from typing import List, Optional
from fastapi import HTTPException, Request
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from datetime import datetime
import os
import re


from collections import defaultdict
import time

# ========== VALIDATION FUNCTIONS ==========

def validate_website(url: str) -> str:
    """Validate and normalize website URL"""
    # Basic URL pattern validation
    url_pattern = re.compile(
        r'^(https?:\/\/)?'  # http:// or https://
        r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'  # domain
        r'(:[0-9]{1,5})?'  # optional port
        r'(\/.*)?$'  # optional path
    )
    
    if not url_pattern.match(url):
        # Try to add https:// if missing
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
            if not url_pattern.match(url):
                raise HTTPException(status_code=422, detail="Invalid website URL format")
    
    return url
    
def validate_filer_info(info_list: List[str]) -> List[str]:
    """Validate filer information"""
    
    validated_info = []
    for item in info_list:
        if not item or len(item.strip()) == 0:
            continue
        if len(item) > 1000:
            raise HTTPException(status_code=422, detail="filer_info item too long (max 1000 chars)")
        validated_info.append(item.strip())
    
    if len(validated_info) == 0:
        raise HTTPException(status_code=422, detail="No valid filer_info provided")
    
    return validated_info

def validate_resolution(text: str) -> str:
    """Validate resolution/reason text"""
    # Security: Check for potential XSS/suspicious patterns
    suspicious_patterns = [
        r'<script.*?>', r'javascript:', r'vbscript:', r'onload=',
        r'onerror=', r'onclick=', r'eval\(', r'document\.',
        r'window\.', r'alert\(', r'prompt\(', r'confirm\(',
        r'<iframe.*?>', r'<object.*?>', r'<embed.*?>'
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            raise HTTPException(status_code=422, detail="Resolution contains suspicious content")
    
    return text.strip()

def validate_legal_document(text: str) -> str:
    """Validate generated legal document"""
    if not text or not isinstance(text, str):
        raise HTTPException(status_code=500, detail="Legal document generation failed")
    
    text = text.strip()
    if len(text) < 100:
        raise HTTPException(status_code=500, detail="Generated legal document is too short")
    
    return text
    
# ========== RATE LIMITING ==========

rate_limit_store = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # 1 minute
RATE_LIMIT_MAX_REQUESTS = 10  # 10 requests per minute

def check_rate_limit(request: Request):
    """Simple rate limiting based on client IP"""
    client_ip = request.client.host
    
    # Clean old timestamps
    current_time = time.time()
    rate_limit_store[client_ip] = [
        ts for ts in rate_limit_store[client_ip] 
        if current_time - ts < RATE_LIMIT_WINDOW
    ]
    
    # Check if limit exceeded
    if len(rate_limit_store[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429, 
            detail=f"Rate limit exceeded. Maximum {RATE_LIMIT_MAX_REQUESTS} requests per minute."
        )
    
    # Add current request timestamp
    rate_limit_store[client_ip].append(current_time)
    
    return True


def extract_contact_chunks(page_text: str, context_chars: 1000) -> Optional[str]:
    """
    Find an email OR phone number in a chunk of text and return the surrounding text with context.
    
    Args:
        page_text: The input text to search through
        context_chars: Number of characters of context to include on each side
    
    Returns:
        The text chunk containing the email or phone number with surrounding context, 
        or None if neither is found
    """
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
    
    phone_pattern = re.compile(
        r'(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|'  # Standard formats
        r'\b\d{3}[-.\s]?\d{4}\b'  # Local formats (7 digits)
    )
    
    email_match = email_pattern.search(page_text)
    phone_match = phone_pattern.search(page_text)
    
    if not email_match and not phone_match:
        print('No contact info in text chunk')
        return None
    
    if email_match and phone_match:
        # Use the earlier match
        match = email_match if email_match.start() < phone_match.start() else phone_match
        print(f'Found both email and phone number')
    elif email_match:
        match = email_match
        print(f'Found email')
    else:
        match = phone_match
        print(f'Found phone number')
    
    # Extract context window
    start = max(0, match.start() - context_chars)
    end = min(len(page_text), match.end() + context_chars)
    
    return page_text[start:end].strip()
    

def legal_doc_to_pdf(legal_text: str, output_filename: str, respondent_name: str, respondent_info=None, filer_info=None, filer_name: str = "filer") -> str:
    """
    Converts a legal document text into a formatted PDF file.
    
    Args:
        legal_text (str): The legal document text from legal_doc_creation()
        output_filename (str): Name for the output PDF file (without .pdf extension)
        respondent_name (str): Name of the company being complained against
        filer_name (str): Name of the person filing the resolution
        respondent_info (List[Dict]): Contact info of the respondent
        filer_info (List[Dict]): Contact info of the filer
    
    Returns:
        str: Path to the generated PDF file
    """
    
    # List of common dash-like characters
    dash_chars = [
        "-",   # hyphen-minus
        "‐",   # hyphen (U+2010)
        "‑",   # non-breaking hyphen (U+2011)
        "‒",   # figure dash (U+2012)
        "–",   # en dash (U+2013) - already en dash
        "—",   # em dash (U+2014)
        "―",   # horizontal bar (U+2015)
        "−",   # minus sign (U+2212)
    ]
    
    en_dash = "–"
    
    for ch in dash_chars:
        legal_text = legal_text.replace(ch, en_dash)
    
    # Ensure the filename has .pdf extension
    if not output_filename.endswith('.pdf'):
        output_filename += '.pdf'
    
    # Create the PDF document
    doc = SimpleDocTemplate(output_filename, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom styles for legal document
    styles.add(ParagraphStyle(
        name='LegalHeader',
        parent=styles['Heading1'],
        fontSize=20,
        textColor='#2c3e50',
        spaceAfter=30,
        alignment=TA_CENTER
    ))
    
    styles.add(ParagraphStyle(
        name='LegalSubheader',
        parent=styles['Heading2'],
        fontSize=15,
        textColor='#34495e',
        spaceAfter=12,
        alignment=TA_LEFT
    ))
    
    styles.add(ParagraphStyle(
        name='LegalBody',
        parent=styles['BodyText'],
        fontSize=11,
        textColor='#2c3e50',
        alignment=TA_JUSTIFY,
        spaceAfter=12
    ))
    
    styles.add(ParagraphStyle(
        name='LegalFooter',
        parent=styles['BodyText'],
        fontSize=11,
        textColor='#7f8c8d',
        alignment=TA_CENTER,
        spaceBefore=20
    ))
    
    # Build the story (content)
    story = []
    
    # Header
    story.append(Paragraph("FORMAL DEMAND FOR RESOLUTION", styles['LegalHeader']))
    story.append(Spacer(1, 5))
    
    # Document metadata
    current_date = datetime.now().strftime("%B %d, %Y")

    # Normalize contact inputs so callers may pass None, a string, a dict, or a list of dicts
    def _normalize_contacts(x):
        if not x:
            return []
        # If a single string was passed, wrap it
        if isinstance(x, str):
            return [{'type': 'info', 'value': x}]
        # If a single dict was passed, wrap it
        if isinstance(x, dict):
            return [x]
        # If it's iterable (list/tuple) assume items are already in expected form
        try:
            return list(x)
        except Exception:
            return [{'type': 'info', 'value': str(x)}]

    def _format_contacts(lst):
        if not lst:
            return 'N/A'
        parts = []
        for info in lst:
            if isinstance(info, dict):
                t = info.get('type', 'info').capitalize()
                v = info.get('value', '')
                parts.append(f"{t}: {v}")
            else:
                parts.append(str(info))
        return ', '.join(parts)

    filer_info = _normalize_contacts(filer_info)
    respondent_info = _normalize_contacts(respondent_info)

    metadata = f"""
    <b>Date:</b> {current_date}<br/>
    <b>Parties Involved:</b> {filer_name} (Filer) vs. {respondent_name} (Respondent)<br/>
    <b>Filer Contact Information:</b> {_format_contacts(filer_info)}<br/>
    <b>Respondent Contact Information:</b> {_format_contacts(respondent_info)}
    """
    story.append(Paragraph(metadata, styles['LegalBody']))
    story.append(Spacer(1, 5))
    
        # Process the legal text - FIXED: Split into paragraphs and handle formatting
    if legal_text:
        # Split the text into paragraphs (assuming double line breaks separate paragraphs)
        paragraphs = legal_text.split('\n\n')
        
        for paragraph in paragraphs:
            if paragraph.strip():  # Only add non-empty paragraphs
                # Replace single line breaks with <br/> tags to preserve line breaks within paragraphs
                formatted_paragraph = paragraph.replace('\n', '<br/>')
                story.append(Paragraph(formatted_paragraph, styles['LegalBody']))
                story.append(Spacer(1, 6))  # Small space between paragraphs
    
    # Add signature section
    story.append(Spacer(1, 30))
    story.append(Paragraph("ACKNOWLEDGEMENT AND SIGNATURE", styles['LegalSubheader']))
    signature_section = f"""
    I, the filer, hereby declare under penalty of perjury that the foregoing is true and correct to the best of my knowledge, information, and belief.
    """
    story.append(Paragraph(signature_section, styles['LegalBody']))
    story.append(Spacer(1, 20))
    
    # Signature lines
    story.append(Paragraph("Signature:__________________________________________________Date:____________", styles['LegalBody']))
    
    # Footer
    story.append(Spacer(1, 40))
    footer_text = f"""
    Confidential Legal Document - Do not distribute without authorization
    """
    story.append(Paragraph(footer_text, styles['LegalFooter']))
    
    try:
        # Build the PDF
        doc.build(story)
        return os.path.abspath(output_filename)
    except Exception as e:
        raise Exception(f"Error generating PDF: {str(e)}")