from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import FileResponse
import tempfile

from ollama_utils import extract_contact_info, legal_doc_creation
from webcrawler import find_contact_url
from utils import (
    validate_legal_document, 
    validate_resolution, 
    validate_website, 
    validate_filer_info, 
    check_rate_limit, 
    extract_contact_chunks, 
    legal_doc_to_pdf
    )

router = APIRouter()

@router.get('/contact-info')
async def get_contact_info(
    request: Request,
    respondent: str = Query(..., min_length=2, max_length=200, description='Name of the company to contact'),
    website: str = Query(..., regex=r'^(https?:\/\/)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(:[0-9]+)?(\/.*)?$', description='Company website URL'),
    filer: str = Query(..., min_length=2, max_length=100, description='Name of the filer'),
    filer_contact_info: list[str] = Query(..., min_length=1, max_length=20, description='Information about the filer'),
    resolution: str = Query(..., min_length=10, max_length=5000, description='Reason for contacting this company')
    
):
    try:
        check_rate_limit(request)
        
        website = validate_website(website)
        filer_contact_info = validate_filer_info(filer_contact_info)
        resolution = validate_resolution(resolution)
        
        # Takes the website URL of the company and finds the contact page
        print(f'Extracting Website...')
        page_text = await find_contact_url(website)
        
        if not page_text or (isinstance(page_text, list) and len(page_text) == 0):
            print('No Website extracted, ending contact extraction.')
            return {
            'respondent': respondent,
            'filer': filer,
            'filer_contact_info': filer_contact_info,
            'reason': resolution,
            'website': website,
            'message': 'No contact information found',
        }
            
        page_chunk = extract_contact_chunks(page_text, context_chars=1000)
        
        # Extracts the contacts information on the contact page
        print(f'Extracting contact info...')
        contacts = extract_contact_info(page_chunk)
        
        response_data = {
            'respondent': respondent,
            'filer': filer,
            'filer_contact_info': filer_contact_info,
            'reason': resolution,
            'website': website,
            'contacts': contacts
        }
        
        
        if contacts:
            try:
                print('Generating Legal document...')
                respondent_data = [contact['value'] for contact in response_data['contacts']]
                filer_data = response_data['filer_contact_info']
                legal_document = legal_doc_creation(
                    company_name=response_data['respondent'],
                    reason=response_data['reason'],
                )
                
                legal_document = validate_legal_document(legal_document)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', prefix='legal_doc_') as tmp_file:
                    temp_pdf_path = tmp_file.name
                    
                print("Converting to PDF...")
                pdf_path = legal_doc_to_pdf(
                    legal_text=legal_document, 
                    output_filename=temp_pdf_path,
                    respondent_name=response_data["respondent"],
                    filer_name=response_data["filer"],
                    respondent_info=respondent_data,
                    filer_info=filer_data
                )
                
                final_pdf_path = pdf_path if pdf_path and isinstance(pdf_path, str) else temp_pdf_path
                
                return FileResponse(
                    path=final_pdf_path,
                    filename=f'Resolution for {response_data["respondent"]}.pdf',
                    media_type='application/pdf'
                )
            
            except HTTPException:
                raise
            except Exception as e:
                print(f'Error generating PDF: {str(e)}')
                # Continue to return JSON response even if PDF generation fails
                response_data['pdf_error'] = str(e)
        
        return response_data
    
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors, rate limiting, etc.)
        raise
        
    except Exception as e:
        print(f'Error in get_contact_info: {str(e)}')
        # Log the full error for debugging
        import traceback
        traceback.print_exc()
        
        # Return user-friendly error
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again later."
        )