import logging
import os
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

TECH_SKILLS = [
    "python", "java", "javascript", "typescript", "c++", "c#", "golang", "rust", "ruby", "php",
    "react", "angular", "vue", "node.js", "express", "django", "flask", "fastapi", "spring",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "jenkins", "git", "github",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "graphql", "rest", "api",
    "machine learning", "deep learning", "tensorflow", "pytorch", "keras", "scikit-learn", "nlp",
    "data analysis", "data science", "pandas", "numpy", "matplotlib", "tableau", "power bi",
    "agile", "scrum", "jira", "ci/cd", "devops", "sre", "linux", "bash", "shell"
]

ROLE_KEYWORDS = {
    "software engineer": ["python", "java", "javascript", "software development", "api", "agile", "scrum", "backend", "frontend"],
    "frontend developer": ["react", "angular", "vue", "javascript", "typescript", "css", "html", "ui", "frontend"],
    "backend developer": ["python", "java", "api", "database", "sql", "backend", "server", "rest", "graphql"],
    "full stack developer": ["react", "node", "python", "javascript", "full stack", "api", "database"],
    "data scientist": ["python", "machine learning", "data analysis", "pandas", "tensorflow", "statistics", "nlp", "data science"],
    "machine learning engineer": ["python", "tensorflow", "pytorch", "machine learning", "deep learning", "ml", "model", "ai"],
    "devops engineer": ["docker", "kubernetes", "aws", "ci/cd", "jenkins", "terraform", "devops", "cloud"],
    "product manager": ["product", "roadmap", "stakeholder", "agile", "scrum", "jira", "planning", "strategy"],
    "ui/ux designer": ["figma", "sketch", "adobe", "ui", "ux", "design", "prototype", "user research", "wireframe"],
    "data analyst": ["sql", "tableau", "power bi", "excel", "data analysis", "pandas", "reporting", "visualization"]
}

class NLPAnalyzer:
    def __init__(self):
        self.nlp = None
        self.embeddings_model = None
        self._load_models()
    
    def _load_models(self):
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_md")
            except OSError:
                try:
                    import subprocess
                    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_md"], capture_output=True)
                    self.nlp = spacy.load("en_core_web_md")
                except Exception as e:
                    logger.exception("Failed to download/load spaCy model 'en_core_web_md': %s", e)
        
        if TRANSFORMERS_AVAILABLE:
            model_name = os.getenv("MODEL_NAME", "all-MiniLM-L6-v2")
            try:
                self.embeddings_model = SentenceTransformer(model_name)
            except Exception as e:
                logger.exception("Failed to load embeddings model '%s': %s", model_name, e)
    
    def extract_skills(self, text: str) -> List[str]:
        text_lower = text.lower()
        found_skills = []
        
        for skill in TECH_SKILLS:
            if skill in text_lower:
                found_skills.append(skill.title() if len(skill) > 3 else skill.upper())
        
        found_skills = list(set(found_skills))
        found_skills.sort()
        return found_skills
    
    def extract_education(self, text: str) -> List[str]:
        education_patterns = [
            r'(?:bachelor|master|phd|doctorate|bs|ms|ba|ma|bsc|msc)\s+(?:of|in)?\s+[\w\s]+',
            r'degree\s+in\s+[\w\s]+',
            r'university\s+of\s+[\w]+',
            r'institute\s+of\s+[\w]+'
        ]
        
        education = []
        for pattern in education_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            education.extend(matches)
        
        return list(set(education))[:5]
    
    def extract_experience_years(self, text: str) -> int:
        patterns = [
            r'(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)',
            r'(\d+)\+?\s*(?:years?|yrs?)\s+(?:in|of)',
            r'experience\s+(?:of\s+)?(\d+)\+?\s*(?:years?|yrs?)',
            r'(\d{4})\s*[-–]\s*(\d{4}|present)'
        ]
        
        years = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        if match[1].lower() == 'present' or match[1].lower() == 'now':
                            years.append(2026 - int(match[0]))
                        else:
                            years.append(int(match[1]) - int(match[0]))
                    else:
                        years.append(int(match))
        
        if years:
            return max(years)
        return 0
    
    def get_text_embedding(self, text: str):
        if self.embeddings_model is None:
            return None
        
        try:
            embedding = self.embeddings_model.encode(text)
            return embedding
        except Exception as e:
            logger.exception("Failed to encode text embedding: %s", e)
            return None
    
    def analyze(self, text: str) -> Dict:
        return {
            "skills": self.extract_skills(text),
            "education": self.extract_education(text),
            "experience_years": self.extract_experience_years(text)
        }