
import ollama
import json
import re
import os
from openai import OpenAI


def legal_doc_creation(company_name: str, reason: str, dev_mode: bool = False, model: str = 'gpt-oss:20b') -> str:
    """
    Creates a legal document for resolving complaints against a company or individual.
    
    Args:
        company_name (str): The name of the company or person being contacted
        reason (str): The reason for the complaint and desired resolution
        model (str): The Ollama model to use
    
    Returns:
        str: A formatted legal document addressing the complaint
    """
    
    prompt = f"""
    Create a simple legal document for filing a formal complaint and requesting resolution.
    
    COMPANY/INDIVIDUAL: {company_name}
    COMPLAINT DETAILS: {reason}
    
    
    Please generate a formal legal document that only includes the following sections:

    1. BACKGROUND: Detail the facts and circumstances of the complaint
    2. SPECIFIC COMPLAINTS: List each specific issue with clear descriptions
    3. LEGAL BASIS: Reference relevant consumer protection laws or regulations
    4. DEMAND FOR RESOLUTION: Specific, actionable steps required to resolve the complaint
    5. TIMELINE: Reasonable deadlines for response and resolution
    6. CONSEQUENCES OF NON-COMPLIANCE: What actions will be taken if unresolved
    
    
    Make the document professional, legally sound, and focused on complete resolution.
    Include specific deadlines and clear expectations. Use formal legal language
    while remaining clear and actionable. Ensure all demands are reasonable and
    directly related to resolving the complaint described. Remove any markdown and output normal text.
    Do not include any sections other than those listed above. Do not include a signature/date section or a title.
    
    """
    
    if dev_mode:
        print(f"dev_mode")
        try:
            stream = ollama.chat(
                model=model,
                messages=[
                    {'role': 'user', 'content': f'{prompt}'}
                ],
            )
            return stream.message.content
            
        except Exception as e:
            return f"Error generating legal document with ollama: {str(e)}"
    else:
        print(f"prod_mode")
        try:
            client = OpenAI(api_key=os.environ.get("DEEPSEEK_KEY"), base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error generating legal document with deepseek: {str(e)}"
    


def extract_contact_info(page_text: str, dev_mode: bool = False, model: str = "gpt-oss:20b") -> list:
        prompt = f"""
You are an intelligent contact information extractor.

Given the following web page text, 
extract all relevant contact information (phone and email, exclude facsimile numbers).

Return exactly a single JSON array and nothing else:
[
  {{
    "type": "phone" | "email",
    "value": "actual contact info",
  }},
  ...
]

Web page text:
\"\"\"
{page_text}
\"\"\"
"""

        if dev_mode:
            print(f"dev_mode")
            try:
                stream = ollama.chat(
                    model=model,
                    messages=[{'role': 'user', 'content': prompt}],
                    stream=True
                )
                
                full_response = ""
            
                for chunk in stream:
                    msg = chunk.get('message', {})
                    if 'content' in msg:
                        full_response += msg['content']
            
                response = full_response.strip()
            
            except Exception as exc:
                print(f'Error calling ollama for contacts: {exc}')
                return []
        else:
            print(f"prod_mode")
            try:
                client = OpenAI(api_key=os.environ.get("DEEPSEEK_KEY"), base_url="https://api.deepseek.com")
                response = client.chat.completions.create(
                    model = "deepseek-chat",
                    messages = [
                        {"role": "user", "content": prompt}
                    ],
                    stream=False
                )
                
                response = response.choices[0].message.content.strip()
            except Exception as exc:
                print(f'Error calling DeepSeek for contacts: {exc}')
                return []
        
        if not response:
            print('Empty response from ollama or deepseek for extract_contact_info')
            return []

        # Extracts the contacts from model generation
        json_match = re.search(r"\[\s*{.*?}\s*\]", response, re.DOTALL)

        # parse Json response with robust error handling
        try:
            if json_match:
                json_text = json_match.group(0)
                if not json_text:
                    print('Regex matched but returned empty string')
                    return []

                contact_data = json.loads(json_text)

                # Ensure we return a list of contacts
                if not isinstance(contact_data, list):
                    print('Parsed JSON is not a list; returning empty list')
                    return []

                return contact_data
            else:
                # No JSON-like array found in the response
                print('No JSON array found in ollama response')
                return []
        except TypeError as te:
            # Handle cases like "'NoneType' object is not iterable"
            if 'NoneType' in str(te):
                print("TypeError during contact parsing: NoneType encountered; returning empty list")
                return []
            print(f'TypeError during parsing contacts: {te}')
            return []
        except json.JSONDecodeError:
            print('Failed to parse JSON')
            return []
        except Exception as exc:
            print(f'Unexpected error parsing contacts: {exc}')
            return []