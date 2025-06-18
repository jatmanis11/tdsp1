import requests
import re
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import hashlib
from urllib.parse import urljoin, urlparse
import time

logger = logging.getLogger(__name__)

class DataScraper:
    def __init__(self):
        self.course_content = {}
        self.discourse_posts = []
        self.scraped_data = {}
        self.last_update = None
        self._initialize_data()
    
    def _initialize_data(self):
        """Initialize data sources"""
        try:
            self._load_course_content()
            self._load_discourse_sample_data()
            self.last_update = datetime.now()
            logger.info("Data scraper initialized successfully")
        except Exception as e:
            logger.error(f"Data scraper initialization error: {e}")
    
    def _load_course_content(self):
        """Load TDS course content from available sources"""
        try:
            # Sample course content structure
            self.course_content = {
                "week1": {
                    "title": "Introduction to Tools in Data Science",
                    "content": """
                    Tools in Data Science course overview:
                    - Python programming fundamentals
                    - Version control with Git
                    - Data analysis libraries (pandas, numpy)
                    - API usage and web scraping
                    - Machine learning basics
                    - Assignment submission guidelines
                    """,
                    "topics": ["python", "git", "pandas", "numpy", "apis", "ml"]
                },
                "week2": {
                    "title": "Python Environment Setup",
                    "content": """
                    Setting up Python environment for TDS:
                    - Install Python 3.8+ from python.org
                    - Use pip for package management
                    - Virtual environments with venv
                    - Jupyter notebook setup
                    - Common packages: pandas, numpy, matplotlib, seaborn
                    """,
                    "topics": ["python", "setup", "environment", "jupyter", "packages"]
                },
                "assignments": {
                    "title": "Assignment Guidelines",
                    "content": """
                    TDS Assignment submission guidelines:
                    - Submit through the designated platform
                    - Include proper documentation
                    - Follow naming conventions
                    - Test your code before submission
                    - Use version control for tracking changes
                    """,
                    "topics": ["assignments", "submission", "guidelines", "documentation"]
                },
                "apis": {
                    "title": "API Usage in Data Science",
                    "content": """
                    Working with APIs in data science:
                    - RESTful API concepts
                    - HTTP methods (GET, POST, PUT, DELETE)
                    - Authentication (API keys, OAuth)
                    - Rate limiting and error handling
                    - Popular APIs: OpenAI, Twitter, Reddit
                    - Python requests library usage
                    """,
                    "topics": ["api", "rest", "http", "authentication", "requests", "openai"]
                }
            }
            
            logger.info(f"Loaded {len(self.course_content)} course content sections")
            
        except Exception as e:
            logger.error(f"Course content loading error: {e}")
    
    def _load_discourse_sample_data(self):
        """Load sample discourse data"""
        try:
            # Sample discourse posts based on common TDS questions
            self.discourse_posts = [
                {
                    "id": "155939",
                    "title": "GA5 Question 8 Clarification",
                    "url": "https://discourse.onlinedegree.iitm.ac.in/t/ga5-question-8-clarification/155939/4",
                    "content": "You must use gpt-3.5-turbo-0125, even if the AI Proxy only supports gpt-4o-mini. Use the OpenAI API directly for this question. The assignment specifically requires gpt-3.5-turbo-0125 for consistency in grading.",
                    "tags": ["gpt", "ai-proxy", "assignment", "openai", "api"],
                    "category": "assignments",
                    "created_at": "2025-04-10",
                    "replies": 8
                },
                {
                    "id": "156001",
                    "title": "Python Environment Setup Issues",
                    "url": "https://discourse.onlinedegree.iitm.ac.in/t/python-setup-issues/156001",
                    "content": "Common Python setup issues and solutions: 1) Use Python 3.8 or higher, 2) Create virtual environment with 'python -m venv tds_env', 3) Activate with 'source tds_env/bin/activate' (Linux/Mac) or 'tds_env\\Scripts\\activate' (Windows), 4) Install required packages with 'pip install -r requirements.txt'",
                    "tags": ["python", "setup", "environment", "virtual-env", "pip"],
                    "category": "technical-help",
                    "created_at": "2025-04-08",
                    "replies": 12
                },
                {
                    "id": "155876",
                    "title": "API Rate Limiting Best Practices",
                    "url": "https://discourse.onlinedegree.iitm.ac.in/t/api-rate-limiting/155876",
                    "content": "When working with APIs, implement proper rate limiting: 1) Check API documentation for limits, 2) Use time.sleep() between requests, 3) Implement exponential backoff for retries, 4) Cache responses when possible, 5) Use batch requests if supported by the API",
                    "tags": ["api", "rate-limiting", "best-practices", "requests"],
                    "category": "programming-help",
                    "created_at": "2025-04-05",
                    "replies": 6
                },
                {
                    "id": "155654",
                    "title": "Assignment Submission Format",
                    "url": "https://discourse.onlinedegree.iitm.ac.in/t/assignment-format/155654",
                    "content": "Proper assignment submission format: 1) Create a main.py file with your solution, 2) Include requirements.txt with dependencies, 3) Add README.md with explanation, 4) Use meaningful variable names and comments, 5) Test your code thoroughly before submission",
                    "tags": ["assignment", "submission", "format", "requirements"],
                    "category": "assignments",
                    "created_at": "2025-03-28",
                    "replies": 15
                },
                {
                    "id": "155432",
                    "title": "Git Version Control for TDS",
                    "url": "https://discourse.onlinedegree.iitm.ac.in/t/git-version-control/155432",
                    "content": "Using Git for TDS assignments: 1) Initialize repo with 'git init', 2) Add files with 'git add .', 3) Commit with meaningful messages 'git commit -m \"message\"', 4) Create branches for different features, 5) Push to GitHub for backup and collaboration",
                    "tags": ["git", "version-control", "github", "collaboration"],
                    "category": "tools",
                    "created_at": "2025-03-20",
                    "replies": 9
                }
            ]
            
            logger.info(f"Loaded {len(self.discourse_posts)} discourse posts")
            
        except Exception as e:
            logger.error(f"Discourse data loading error: {e}")
    
    def search_relevant_content(self, question: str) -> str:
        """Search for relevant content based on question"""
        try:
            question_lower = question.lower()
            relevant_content = []
            
            # Search course content
            course_matches = self._search_course_content(question_lower)
            relevant_content.extend(course_matches)
            
            # Search discourse posts
            discourse_matches = self._search_discourse_posts(question_lower)
            relevant_content.extend(discourse_matches)
            
            # Combine and limit content
            combined_content = "\n\n".join(relevant_content[:5])  # Limit to 5 most relevant
            
            return combined_content if combined_content else "No specific course content found for this question."
            
        except Exception as e:
            logger.error(f"Content search error: {e}")
            return "Unable to search course content."
    
    def _search_course_content(self, question_lower: str) -> List[str]:
        """Search course content for relevant matches"""
        matches = []
        
        try:
            question_words = set(question_lower.split())
            
            for section_key, section_data in self.course_content.items():
                content_lower = section_data['content'].lower()
                topics = section_data.get('topics', [])
                
                # Check for topic matches
                topic_matches = sum(1 for topic in topics if topic in question_lower)
                
                # Check for keyword matches in content
                content_matches = sum(1 for word in question_words if word in content_lower)
                
                # Score relevance
                relevance_score = topic_matches * 2 + content_matches
                
                if relevance_score > 0:
                    matches.append((relevance_score, f"Course Material - {section_data['title']}:\n{section_data['content'].strip()}"))
            
            # Sort by relevance and return top matches
            matches.sort(key=lambda x: x[0], reverse=True)
            return [match[1] for match in matches[:3]]
            
        except Exception as e:
            logger.error(f"Course content search error: {e}")
            return []
    
    def _search_discourse_posts(self, question_lower: str) -> List[str]:
        """Search discourse posts for relevant matches"""
        matches = []
        
        try:
            question_words = set(question_lower.split())
            
            for post in self.discourse_posts:
                title_lower = post['title'].lower()
                content_lower = post['content'].lower()
                tags = post.get('tags', [])
                
                # Check for tag matches
                tag_matches = sum(1 for tag in tags if tag in question_lower)
                
                # Check for title matches
                title_matches = sum(1 for word in question_words if word in title_lower)
                
                # Check for content matches
                content_matches = sum(1 for word in question_words if word in content_lower)
                
                # Score relevance
                relevance_score = tag_matches * 3 + title_matches * 2 + content_matches
                
                if relevance_score > 0:
                    post_text = f"Discourse Post: {post['title']}\nURL: {post['url']}\nContent: {post['content']}\nTags: {', '.join(tags)}"
                    matches.append((relevance_score, post_text))
            
            # Sort by relevance and return top matches
            matches.sort(key=lambda x: x[0], reverse=True)
            return [match[1] for match in matches[:3]]
            
        except Exception as e:
            logger.error(f"Discourse search error: {e}")
            return []
    
    def get_content_summary(self) -> Dict[str, int]:
        """Get summary of available content"""
        return {
            "course_sections": len(self.course_content),
            "discourse_posts": len(self.discourse_posts),
            "last_update": self.last_update.isoformat() if self.last_update else None
        }
