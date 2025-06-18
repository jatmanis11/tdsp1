import json
import base64
import logging
from typing import Dict, Any, List
import re

logger = logging.getLogger(__name__)

def validate_response_structure(response: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and ensure proper response structure"""
    try:
        # Ensure required fields exist
        if not isinstance(response, dict):
            raise ValueError("Response must be a dictionary")
        
        if 'answer' not in response:
            response['answer'] = "Unable to generate a proper response."
        
        if 'links' not in response:
            response['links'] = []
        
        # Validate and clean answer
        answer = response['answer']
        if not isinstance(answer, str):
            answer = str(answer) if answer is not None else "No answer provided."
        
        # Clean answer text
        answer = answer.strip()
        if not answer:
            answer = "Unable to provide a meaningful answer."
        
        # Ensure answer is not too long
        if len(answer) > 2000:
            answer = answer[:1997] + "..."
        
        response['answer'] = answer
        
        # Validate and clean links
        links = response['links']
        if not isinstance(links, list):
            links = []
        
        validated_links = []
        for link in links:
            if isinstance(link, dict) and 'url' in link and 'text' in link:
                url = str(link['url']).strip()
                text = str(link['text']).strip()
                
                # Basic URL validation
                if url and text and url.startswith('http'):
                    validated_links.append({
                        'url': url,
                        'text': text
                    })
        
        # Ensure at least one link exists
        if not validated_links:
            validated_links.append({
                'url': 'https://discourse.onlinedegree.iitm.ac.in/',
                'text': 'TDS Course Forum'
            })
        
        response['links'] = validated_links
        
        # Test JSON serialization
        json.dumps(response)
        
        return response
        
    except Exception as e:
        logger.error(f"Response validation error: {e}")
        return {
            'answer': 'Response validation failed. Please try again.',
            'links': [{'url': 'https://discourse.onlinedegree.iitm.ac.in/', 'text': 'TDS Course Forum'}]
        }

def process_image_data(image_b64: str) -> str:
    """Process base64 image data and return context"""
    try:
        if not image_b64:
            return ""
        
        # Decode base64 image
        image_data = base64.b64decode(image_b64)
        
        # Get image size for context
        image_size = len(image_data)
        
        # Return basic image context
        return f"Image provided ({image_size} bytes). This appears to be a screenshot or diagram related to the question."
        
    except Exception as e:
        logger.error(f"Image processing error: {e}")
        return "Image provided but could not be processed."

def extract_keywords(text: str) -> List[str]:
    """Extract keywords from text for better searching"""
    try:
        # Convert to lowercase and split
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter out common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does',
            'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
            'us', 'them', 'my', 'your', 'his', 'our', 'their'
        }
        
        # Filter keywords
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]
        
        return list(set(keywords))  # Remove duplicates
        
    except Exception as e:
        logger.error(f"Keyword extraction error: {e}")
        return []

def format_links_for_context(links: List[str]) -> str:
    """Format links for inclusion in AI context"""
    try:
        if not links:
            return ""
        
        formatted_links = []
        for link in links[:5]:  # Limit to 5 links
            if isinstance(link, str) and link.startswith('http'):
                formatted_links.append(f"- {link}")
        
        return f"Relevant links:\n" + "\n".join(formatted_links) if formatted_links else ""
        
    except Exception as e:
        logger.error(f"Link formatting error: {e}")
        return ""
