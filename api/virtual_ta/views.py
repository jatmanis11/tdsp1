import json
import base64
import logging
import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.utils import timezone
from .ai_service import MultiAIService
from .data_scraper import DataScraper

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def virtual_ta_api(request):
    """Main API endpoint for TDS Virtual TA"""
    start_time = time.time()
    
    try:
        # Parse request data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in request")
            return JsonResponse({
                'answer': 'Invalid JSON format in request. Please check your request structure.',
                'links': [{'url': 'https://discourse.onlinedegree.iitm.ac.in/', 'text': 'TDS Course Forum'}]
            }, status=400)
        
        question = data.get('question', '').strip()
        image_b64 = data.get('image', '')
        
        # Validate input
        if not question:
            return JsonResponse({
                'answer': 'Please provide a question for the TDS Virtual TA.',
                'links': [{'url': 'https://discourse.onlinedegree.iitm.ac.in/', 'text': 'TDS Course Forum'}]
            }, status=400)
        
        if len(question) > 1000:
            return JsonResponse({
                'answer': 'Question is too long. Please keep it under 1000 characters.',
                'links': [{'url': 'https://discourse.onlinedegree.iitm.ac.in/', 'text': 'TDS Course Forum'}]
            }, status=400)
        
        # Log request for monitoring
        logger.info(f"Processing question: {question[:100]}{'...' if len(question) > 100 else ''}")
        
        # Check rate limiting per IP
        client_ip = get_client_ip(request)
        if is_rate_limited(client_ip):
            return JsonResponse({
                'answer': 'Too many requests. Please wait a moment before asking another question.',
                'links': [{'url': 'https://discourse.onlinedegree.iitm.ac.in/', 'text': 'TDS Course Forum'}]
            }, status=429)
        
        # Initialize services
        try:
            ai_service = MultiAIService()
            data_scraper = DataScraper()
        except Exception as e:
            logger.error(f"Service initialization error: {e}")
            return JsonResponse({
                'answer': 'Unable to initialize TDS Virtual TA services. Please try again later.',
                'links': [{'url': 'https://discourse.onlinedegree.iitm.ac.in/', 'text': 'TDS Course Forum'}]
            }, status=500)
        
        # Get relevant context from course materials
        try:
            context = data_scraper.search_relevant_content(question)
            logger.info(f"Found context: {len(context)} characters")
        except Exception as e:
            logger.error(f"Context retrieval error: {e}")
            context = "Unable to retrieve specific course context."
        
        # Process image if provided
        image_context = ""
        if image_b64:
            try:
                image_context = process_image_data(image_b64)
                logger.info("Image processed successfully")
            except Exception as e:
                logger.warning(f"Image processing failed: {e}")
                image_context = "Image provided but could not be processed."
        
        # Generate answer using AI with fallbacks
        try:
            answer_data = ai_service.generate_answer(question, context, image_context)
            logger.info("Response generated successfully")
        except Exception as e:
            logger.error(f"AI generation error: {e}")
            answer_data = {
                'answer': 'Unable to process your question at the moment. Please try again or post on the discourse forum.',
                'links': [{'url': 'https://discourse.onlinedegree.iitm.ac.in/', 'text': 'TDS Course Forum'}]
            }
        
        # Validate response structure
        try:
            validated_response = validate_response_structure(answer_data)
        except Exception as e:
            logger.error(f"Response validation error: {e}")
            validated_response = {
                'answer': 'Response validation failed. Please try again.',
                'links': [{'url': 'https://discourse.onlinedegree.iitm.ac.in/', 'text': 'TDS Course Forum'}]
            }
        
        # Log processing time
        processing_time = time.time() - start_time
        logger.info(f"Request processed in {processing_time:.2f} seconds")
        
        # Warn if approaching timeout
        if processing_time > 25:
            logger.warning(f"Long processing time: {processing_time:.2f} seconds")
        
        # Record successful request for rate limiting
        record_request(client_ip)
        
        return JsonResponse(validated_response, json_dumps_params={'ensure_ascii': False})
        
    except Exception as e:
        logger.error(f"Unexpected API error: {e}")
        return JsonResponse({
            'answer': 'An unexpected error occurred. Please try again or contact support through the discourse forum.',
            'links': [{'url': 'https://discourse.onlinedegree.iitm.ac.in/', 'text': 'TDS Course Forum'}]
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """Health check endpoint for monitoring"""
    try:
        # Quick service checks
        ai_service = MultiAIService()
        data_scraper = DataScraper()
        
        health_data = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'ai_service': {
                'initialized': ai_service.gemini_service.is_initialized,
                'request_count': getattr(ai_service, 'request_count', 0),
                'daily_limit': getattr(ai_service, 'daily_limit', 50)
            },
            'data_scraper': {
                'course_sections': len(data_scraper.course_content),
                'discourse_posts': len(data_scraper.discourse_posts)
            },
            'cache_status': 'available' if cache else 'unavailable'
        }
        
        return JsonResponse(health_data)
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def api_info(request):
    """API information endpoint"""
    return JsonResponse({
        'name': 'TDS Virtual TA',
        'version': '1.0.0',
        'description': 'Virtual Teaching Assistant for IIT Madras Tools in Data Science course',
        'endpoints': {
            'main': '/api/',
            'health': '/api/health/',
            'info': '/api/info/'
        },
        'usage': {
            'method': 'POST',
            'content_type': 'application/json',
            'required_fields': ['question'],
            'optional_fields': ['image']
        },
        'rate_limits': {
            'requests_per_minute': 10,
            'requests_per_hour': 100
        }
    })

# Helper functions

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def is_rate_limited(ip):
    """Check if IP is rate limited"""
    try:
        # Rate limits: 10 requests per minute, 100 per hour
        minute_key = f"rate_limit_minute:{ip}:{int(time.time() // 60)}"
        hour_key = f"rate_limit_hour:{ip}:{int(time.time() // 3600)}"
        
        minute_count = cache.get(minute_key, 0)
        hour_count = cache.get(hour_key, 0)
        
        if minute_count >= 10 or hour_count >= 100:
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Rate limiting error: {e}")
        return False

def record_request(ip):
    """Record request for rate limiting"""
    try:
        minute_key = f"rate_limit_minute:{ip}:{int(time.time() // 60)}"
        hour_key = f"rate_limit_hour:{ip}:{int(time.time() // 3600)}"
        
        # Increment counters
        minute_count = cache.get(minute_key, 0) + 1
        hour_count = cache.get(hour_key, 0) + 1
        
        cache.set(minute_key, minute_count, 60)  # 1 minute TTL
        cache.set(hour_key, hour_count, 3600)   # 1 hour TTL
        
    except Exception as e:
        logger.error(f"Request recording error: {e}")

def process_image_data(image_b64: str) -> str:
    """Process base64 image data"""
    try:
        if not image_b64:
            return ""
        
        # Decode base64 image
        image_data = base64.b64decode(image_b64)
        image_size = len(image_data)
        
        # Basic image validation
        if image_size > 10 * 1024 * 1024:  # 10MB limit
            return "Image too large (max 10MB)."
        
        # Check for common image formats
        if image_data.startswith(b'\xff\xd8\xff'):
            format_type = "JPEG"
        elif image_data.startswith(b'\x89PNG'):
            format_type = "PNG"
        elif image_data.startswith(b'GIF'):
            format_type = "GIF"
        elif image_data.startswith(b'RIFF') and b'WEBP' in image_data[:12]:
            format_type = "WEBP"
        else:
            format_type = "Unknown"
        
        return f"Image provided ({format_type}, {image_size} bytes). This appears to be a screenshot or diagram related to the TDS question."
        
    except Exception as e:
        logger.error(f"Image processing error: {e}")
        return "Image provided but could not be processed."

def validate_response_structure(response: dict) -> dict:
    """Validate and ensure proper response structure"""
    try:
        # Ensure required fields
        if not isinstance(response, dict):
            raise ValueError("Response must be a dictionary")
        
        if 'answer' not in response:
            response['answer'] = "Unable to generate a proper response."
        
        if 'links' not in response:
            response['links'] = []
        
        # Validate answer
        answer = response['answer']
        if not isinstance(answer, str):
            answer = str(answer) if answer is not None else "No answer provided."
        
        answer = answer.strip()
        if not answer:
            answer = "Unable to provide a meaningful answer."
        
        # Limit answer length
        if len(answer) > 2000:
            answer = answer[:1997] + "..."
        
        response['answer'] = answer
        
        # Validate links
        links = response['links']
        if not isinstance(links, list):
            links = []
        
        validated_links = []
        for link in links:
            if isinstance(link, dict) and 'url' in link and 'text' in link:
                url = str(link['url']).strip()
                text = str(link['text']).strip()
                
                if url and text and url.startswith('http'):
                    validated_links.append({'url': url, 'text': text})
        
        # Ensure at least one link
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
