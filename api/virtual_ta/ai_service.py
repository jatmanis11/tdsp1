import google.generativeai as genai
from django.conf import settings
import logging
import json
import re
import time
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.model = None
        self.is_initialized = False
        self._initialize_gemini()
    
    def _initialize_gemini(self):
        """Initialize Gemini AI service with Flash model for higher free limits"""
        try:
            if settings.GEMINI_API_KEY:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                
                # Use Flash model - 15 RPM vs 2 RPM for Pro
                model_name = self._get_available_model()
                self.model = genai.GenerativeModel(model_name)
                self.is_initialized = True
                logger.info(f"Gemini AI service initialized with model: {model_name}")
            else:
                logger.warning("No Gemini API key configured")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.is_initialized = False
    
    def _get_available_model(self):
        """Get Flash model for higher free tier limits"""
        try:
            # Flash models have much higher free tier limits
            preferred_models = [
                'models/gemini-1.5-flash-latest',    # 15 RPM free tier
                'models/gemini-1.5-flash',           # Higher limits
                'models/gemini-1.5-flash-8b-latest', # Even higher limits
                'models/gemini-1.0-pro-latest'       # Backup
            ]
            
            try:
                available_models = []
                for model in genai.list_models():
                    if 'generateContent' in model.supported_generation_methods:
                        available_models.append(model.name)
                
                logger.info(f"Available models: {available_models}")
                
                for preferred in preferred_models:
                    if preferred in available_models:
                        logger.info(f"Selected model: {preferred}")
                        return preferred
            except:
                pass
            
            # Default to Flash if listing fails
            return 'models/gemini-1.5-flash-latest'
            
        except Exception as e:
            logger.error(f"Model selection error: {e}")
            return 'models/gemini-1.5-flash-latest'
    
    def generate_answer(self, question: str, context: str, image_context: str = "") -> Dict[str, Any]:
        """Generate answer using Gemini with fallback"""
        try:
            if not self.is_initialized or not self.model:
                logger.warning("AI service not initialized, using fallback")
                return self._fallback_response(question)
            
            # Create prompt
            prompt = self._create_prompt(question, context, image_context)
            
            # Generate with retry
            ai_response = self._generate_with_retry(prompt)
            
            if ai_response:
                return self._process_ai_response(ai_response, context, question)
            else:
                return self._fallback_response(question)
            
        except Exception as e:
            logger.error(f"AI Service Error: {e}")
            return self._fallback_response(question)
    
    def _create_prompt(self, question: str, context: str, image_context: str) -> str:
        """Create comprehensive prompt for AI"""
        prompt = f"""You are a Teaching Assistant for Tools in Data Science (TDS) at IIT Madras.

COURSE CONTEXT:
{context[:800]}

{image_context}

STUDENT QUESTION: {question}

INSTRUCTIONS:
- Provide helpful, accurate answers based on TDS course content
- Be specific about assignments, tools (Python, Git, APIs), and requirements
- Keep responses concise but informative
- Reference course materials when relevant

Answer the student's question directly and helpfully."""
        return prompt
    
    def _generate_with_retry(self, prompt: str, max_retries: int = 2) -> Optional[str]:
        """Generate with minimal retries to avoid quota issues"""
        for attempt in range(max_retries):
            try:
                generation_config = genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.8,
                    max_output_tokens=500,  # Reduced to save quota
                )
                
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                
                if response and response.text:
                    return response.text.strip()
                    
            except Exception as e:
                error_str = str(e).lower()
                logger.error(f"AI generation attempt {attempt + 1} failed: {e}")
                
                # Don't retry on quota errors
                if "429" in error_str or "quota" in error_str or "exceeded" in error_str:
                    logger.warning("Quota exceeded, stopping retries")
                    break
                
                if attempt < max_retries - 1:
                    time.sleep(1)
                    
        return None
    
    def _process_ai_response(self, ai_response: str, context: str, question: str) -> Dict[str, Any]:
        """Process AI response into required format"""
        try:
            answer = self._clean_answer_text(ai_response)
            links = self._extract_relevant_links(context, question)
            
            response = {
                "answer": answer,
                "links": links
            }
            
            # Test JSON serialization
            json.dumps(response)
            return response
            
        except Exception as e:
            logger.error(f"Response processing error: {e}")
            return self._fallback_response(question)
    
    def _clean_answer_text(self, raw_text: str) -> str:
        """Clean and validate answer text"""
        if not raw_text or not isinstance(raw_text, str):
            return "I couldn't generate a proper response."
        
        # Clean text
        cleaned = re.sub(r'\s+', ' ', raw_text.strip())
        
        # Ensure reasonable length
        if len(cleaned) > 1200:
            sentences = cleaned.split('. ')
            truncated = ""
            for sentence in sentences:
                if len(truncated + sentence) > 1000:
                    break
                truncated += sentence + '. '
            cleaned = truncated.strip()
        
        return cleaned if cleaned else "I couldn't generate a proper response."
    
    def _extract_relevant_links(self, context: str, question: str) -> List[Dict[str, str]]:
        """Extract relevant links from context"""
        links = []
        
        try:
            # Extract discourse URLs
            discourse_urls = re.findall(
                r'https://discourse\.onlinedegree\.iitm\.ac\.in/t/[^/\s]+/\d+(?:/\d+)?',
                context
            )
            
            unique_urls = list(set(discourse_urls))[:2]  # Limit to 2
            
            for i, url in enumerate(unique_urls):
                topic_match = re.search(r'/t/([^/]+)/', url)
                if topic_match:
                    topic_name = topic_match.group(1).replace('-', ' ').title()
                    link_text = f"{topic_name} Discussion"
                else:
                    link_text = f"Related Discussion {i + 1}"
                
                links.append({"url": url, "text": link_text})
            
            # Add contextual links based on question
            if not links:
                question_lower = question.lower()
                if any(word in question_lower for word in ['assignment', 'homework', 'submit']):
                    links.append({
                        "url": "https://discourse.onlinedegree.iitm.ac.in/c/degree-program/tools-in-data-science/",
                        "text": "TDS Assignment Help"
                    })
                else:
                    links.append({
                        "url": "https://discourse.onlinedegree.iitm.ac.in/",
                        "text": "TDS Course Forum"
                    })
            
        except Exception as e:
            logger.error(f"Link extraction error: {e}")
            links = [{"url": "https://discourse.onlinedegree.iitm.ac.in/", "text": "TDS Course Forum"}]
        
        return links
    
    def _fallback_response(self, question: str) -> Dict[str, Any]:
        """Intelligent fallback based on question analysis"""
        question_lower = question.lower() if question else ""
        
        # Analyze question and provide contextual responses
        if any(word in question_lower for word in ['gpt', 'openai', 'api', 'model', 'ai']):
            answer = "For TDS assignments requiring specific AI models like GPT-3.5-turbo, use the OpenAI API directly as specified in the assignment requirements. The assignment may specify a particular model version for consistency in grading."
            link_text = "AI Model Usage Help"
            
        elif any(word in question_lower for word in ['python', 'setup', 'install', 'environment', 'pip']):
            answer = "For Python setup in TDS: 1) Install Python 3.8+, 2) Create virtual environment: 'python -m venv tds_env', 3) Activate: 'source tds_env/bin/activate' (Linux/Mac) or 'tds_env\\Scripts\\activate' (Windows), 4) Install packages: 'pip install -r requirements.txt'."
            link_text = "Python Setup Help"
            
        elif any(word in question_lower for word in ['assignment', 'submit', 'deadline', 'homework', 'ga']):
            answer = "For TDS assignments: 1) Follow the specified format, 2) Include proper documentation and comments, 3) Test your code thoroughly, 4) Submit through the designated platform, 5) Check discourse for assignment-specific clarifications and deadlines."
            link_text = "Assignment Guidelines"
            
        elif any(word in question_lower for word in ['git', 'version', 'control', 'github', 'commit']):
            answer = "For Git in TDS: 1) Initialize: 'git init', 2) Add files: 'git add .', 3) Commit: 'git commit -m \"meaningful message\"', 4) Push to GitHub: 'git push origin main'. Use version control for all assignments."
            link_text = "Git Version Control"
            
        elif any(word in question_lower for word in ['error', 'debug', 'fix', 'problem', 'issue']):
            answer = "For debugging in TDS: 1) Read error messages carefully, 2) Check your code syntax and logic, 3) Use print statements for debugging, 4) Search discourse for similar issues, 5) Share your error on the forum for help."
            link_text = "Debugging Help"
            
        else:
            answer = "I'm currently experiencing high demand. Please check the TDS course materials on the learning platform or post your question on the discourse forum where TAs and fellow students can provide detailed assistance."
            link_text = "TDS Course Forum"
        
        return {
            "answer": answer,
            "links": [{"url": "https://discourse.onlinedegree.iitm.ac.in/", "text": link_text}]
        }


class MultiAIService:
    """Enhanced AI service with rate limiting and fallbacks"""
    
    def __init__(self):
        self.gemini_service = AIService()
        self.last_request_time = 0
        self.min_delay = 5  # 5 seconds between requests for safety
        self.request_count = 0
        self.daily_limit = 50  # Conservative daily limit
        
    def generate_answer(self, question: str, context: str, image_context: str = "") -> Dict[str, Any]:
        """Generate answer with rate limiting and fallbacks"""
        
        # Check daily limit
        if self.request_count >= self.daily_limit:
            logger.warning("Daily request limit reached")
            return self._intelligent_fallback(question, context)
        
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_delay:
            wait_time = self.min_delay - time_since_last
            logger.info(f"Rate limiting: waiting {wait_time:.1f} seconds")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
        self.request_count += 1
        
        # Try Gemini
        try:
            if self.gemini_service.is_initialized:
                response = self.gemini_service.generate_answer(question, context, image_context)
                
                # Check if it's not a fallback response
                if (response and response.get('answer') and 
                    "currently unable to process" not in response.get('answer', '').lower()):
                    return response
                    
        except Exception as e:
            logger.error(f"Gemini failed: {e}")
        
        # Use intelligent fallback
        return self._intelligent_fallback(question, context)
    
    def _intelligent_fallback(self, question: str, context: str) -> Dict[str, Any]:
        """Advanced fallback with context analysis"""
        question_lower = question.lower()
        
        # Extract relevant information from context
        context_info = ""
        if context and len(context) > 50:
            # Find relevant sentences from context
            sentences = context.split('.')
            relevant_sentences = []
            
            question_words = set(question_lower.split())
            for sentence in sentences[:10]:  # Check first 10 sentences
                sentence_lower = sentence.lower()
                matches = sum(1 for word in question_words if word in sentence_lower and len(word) > 3)
                if matches > 0:
                    relevant_sentences.append(sentence.strip())
            
            if relevant_sentences:
                context_info = f"Based on course materials: {'. '.join(relevant_sentences[:2])}. "
        
        # Generate contextual response
        if any(word in question_lower for word in ['gpt', 'openai', 'api', 'model']):
            answer = f"{context_info}For AI model questions in TDS: Use the specific model mentioned in the assignment (like gpt-3.5-turbo-0125) through the OpenAI API directly, even if proxies support different models."
            
        elif any(word in question_lower for word in ['python', 'setup', 'environment']):
            answer = f"{context_info}For Python in TDS: Install Python 3.8+, create virtual environment with 'python -m venv tds_env', activate it, then install required packages with pip."
            
        elif any(word in question_lower for word in ['assignment', 'submit', 'homework']):
            answer = f"{context_info}For TDS assignments: Follow the submission format, include documentation, test thoroughly, and check discourse for specific requirements and deadlines."
            
        else:
            answer = f"{context_info}For detailed help with your TDS question, please post on the discourse forum where TAs and students can provide comprehensive assistance."
        
        return {
            "answer": answer,
            "links": self._extract_links_from_context(context)
        }
    
    def _extract_links_from_context(self, context: str) -> List[Dict[str, str]]:
        """Extract links from context"""
        links = []
        
        # Extract discourse URLs
        import re
        urls = re.findall(r'https://discourse\.onlinedegree\.iitm\.ac\.in/t/[^/\s]+/\d+(?:/\d+)?', context)
        
        for i, url in enumerate(urls[:2]):
            links.append({
                "url": url,
                "text": f"Related Discussion {i + 1}"
            })
        
        if not links:
            links.append({
                "url": "https://discourse.onlinedegree.iitm.ac.in/",
                "text": "TDS Course Forum"
            })
        
        return links
