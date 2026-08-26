import logging
import os
from typing import List, Dict, Tuple
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

ROLE_DESCRIPTIONS = {
    "Software Engineer": "Software engineer designs, develops, tests and maintains scalable software applications using languages like Python, Java, JavaScript or C++. Builds REST APIs, works with SQL and NoSQL databases, writes unit and integration tests, follows system design principles, participates in code reviews and agile sprints, and ships reliable production code.",
    "Frontend Developer": "Frontend developer builds responsive, accessible user interfaces with HTML, CSS, JavaScript and TypeScript using React, Next.js, Angular or Vue. Implements state management, performance optimization, accessibility, cross-browser compatibility, and design systems. Collaborates with UX designers and backend engineers to ship pixel-perfect web experiences.",
    "Backend Developer": "Backend developer builds secure, scalable server-side systems with Python, Java, Node.js or Go using frameworks like FastAPI, Spring or Express. Designs REST and GraphQL APIs, data models and database schemas with SQL, PostgreSQL, MongoDB and Redis. Handles authentication, caching, message queues, and cloud deployment on AWS or GCP.",
    "Full Stack Developer": "Full stack developer ships end-to-end features across frontend and backend using React, Next.js, Node.js, Python and SQL. Builds REST APIs, integrates databases, implements authentication, manages deployment with Docker and CI/CD, and owns features from UI to database and infrastructure.",
    "Data Scientist": "Data scientist extracts insights from structured and unstructured data using Python, SQL, pandas, NumPy and statistical modeling. Builds machine learning models, performs feature engineering and data visualization, runs experiments and communicates findings to drive business decisions.",
    "Machine Learning Engineer": "Machine learning engineer builds, trains and deploys ML and deep learning models with Python, TensorFlow, PyTorch and scikit-learn. Handles data pipelines, model optimization, MLOps, experiment tracking, A/B testing and scalable inference services in production.",
    "DevOps Engineer": "DevOps engineer automates infrastructure and delivery with CI/CD, Docker, Kubernetes, Terraform, Jenkins and GitHub Actions. Manages AWS, GCP or Azure, implements monitoring, logging, alerting and incident response, and ensures high availability and security of production systems.",
    "Product Manager": "Product manager owns product strategy, roadmaps and prioritization. Defines requirements, runs user research, analyzes metrics, collaborates with engineering and design through agile delivery, and drives product outcomes with stakeholders.",
    "UI/UX Designer": "UI/UX designer researches users, creates journey maps, wireframes, high-fidelity prototypes and design systems in Figma, Sketch or Adobe XD. Focuses on usability, accessibility, interaction design and user testing to deliver intuitive digital experiences.",
    "Data Analyst": "Data analyst queries and models data with SQL, Python, Excel, Tableau and Power BI. Builds dashboards and reports, performs data cleaning and visualization, and translates analysis into business insights and recommendations."
}

# Canonicalize variant surface forms to the same keyword bucket
SYNONYM_MAP = {
    "postgresql": "sql",
    "postgres": "sql",
    "mysql": "sql",
    "mongodb": "database",
    "redis": "database",
    "dynamodb": "database",
    "node.js": "node",
    "nodejs": "node",
    "express": "api",
    "express.js": "api",
    "fastapi": "api",
    "nestjs": "node",
    "next.js": "react",
    "nextjs": "react",
    "vue.js": "vue",
    "tailwind": "css",
    "tailwind css": "css",
    "pytorch": "tensorflow",
    "scikit-learn": "machine learning",
    "sklearn": "machine learning",
}

class RoleMatcher:
    def __init__(self):
        self.embeddings_model = None
        self.role_embeddings = {}
        self._load_models()
    
    def _load_models(self):
        if TRANSFORMERS_AVAILABLE:
            model_name = os.getenv("MODEL_NAME", "all-MiniLM-L6-v2")
            try:
                self.embeddings_model = SentenceTransformer(model_name)
                self._embed_roles()
            except Exception as e:
                logger.exception("Could not load embeddings model '%s': %s", model_name, e)
    
    def _embed_roles(self):
        if self.embeddings_model is None:
            return
        
        roles = list(ROLE_DESCRIPTIONS.keys())
        descriptions = list(ROLE_DESCRIPTIONS.values())
        
        try:
            embeddings = self.embeddings_model.encode(descriptions)
            for role, embedding in zip(roles, embeddings):
                self.role_embeddings[role] = embedding
        except Exception as e:
            logger.exception("Could not embed role descriptions: %s", e)
    
    def _normalize_token(self, token: str) -> str:
        t = token.strip().lower()
        return SYNONYM_MAP.get(t, t)

    def calculate_keyword_match(self, resume_skills: List[str], target_role: str) -> float:
        target_role_lower = target_role.lower()
        
        role_keyword_sets = {
            "software engineer": ["python", "java", "javascript", "typescript", "software", "api", "development", "system design", "testing", "git"],
            "frontend developer": ["react", "angular", "vue", "javascript", "typescript", "css", "html", "ui", "next.js", "accessibility"],
            "backend developer": ["python", "java", "node", "api", "database", "sql", "backend", "server", "rest", "graphql", "caching"],
            "full stack developer": ["react", "node", "python", "javascript", "typescript", "database", "api", "docker"],
            "data scientist": ["python", "machine learning", "data", "analysis", "pandas", "tensorflow", "statistics", "visualization"],
            "machine learning engineer": ["python", "tensorflow", "pytorch", "machine learning", "deep learning", "model", "mlops", "deployment"],
            "devops engineer": ["docker", "kubernetes", "aws", "ci/cd", "jenkins", "terraform", "cloud", "monitoring", "gcp", "azure"],
            "product manager": ["product", "roadmap", "stakeholder", "agile", "planning", "strategy", "metrics", "research"],
            "ui/ux designer": ["figma", "sketch", "ui", "ux", "design", "prototype", "user", "research", "wireframe"],
            "data analyst": ["sql", "tableau", "excel", "data", "analysis", "reporting", "power bi", "visualization"]
        }
        
        role_keywords = []
        for role_name, keywords in role_keyword_sets.items():
            if role_name in target_role_lower or any(kw in target_role_lower for kw in keywords):
                role_keywords = keywords
                break
        
        if not role_keywords:
            role_keywords = target_role_lower.split()
        
        normalized_skills = [self._normalize_token(s) for s in resume_skills]
        normalized_keywords = [self._normalize_token(k) for k in role_keywords]
        # also expand skills via synonym values so "PostgreSQL" counts as "sql"
        expanded_skills = set(normalized_skills)
        for s in normalized_skills:
            if s in SYNONYM_MAP.values():
                expanded_skills.add(s)
        # count distinct keyword buckets hit (softer than strict matched/len)
        hit_buckets = sum(1 for kw in normalized_keywords if any(kw in skill or skill in kw for skill in expanded_skills))
        return min(hit_buckets / max(len(normalized_keywords), 1), 1.0)
    
    def _chunk_text(self, text: str, chunk_chars: int = 800, overlap: int = 100) -> List[str]:
        if len(text) <= chunk_chars:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            chunks.append(text[start:start + chunk_chars])
            start += chunk_chars - overlap
        return chunks

    def calculate_semantic_similarity(self, resume_text: str, target_role: str) -> float:
        if self.embeddings_model is None:
            return 0.5
        
        target_role_key = target_role
        for role_name in ROLE_DESCRIPTIONS.keys():
            if role_name.lower() in target_role.lower():
                target_role_key = role_name
                break
        
        role_description = ROLE_DESCRIPTIONS.get(target_role_key, target_role)
        
        try:
            chunks = self._chunk_text(resume_text, chunk_chars=900, overlap=150)
            chunk_embeddings = self.embeddings_model.encode(chunks)
            role_embedding = self.embeddings_model.encode([role_description])
            sims = cosine_similarity(chunk_embeddings, role_embedding).flatten()
            # best chunk + mean gives robustness without single-chunk noise
            best = float(max(sims))
            mean = float(sum(sims) / len(sims))
            return max(best, 0.6 * best + 0.4 * mean)
        except Exception as e:
            logger.exception("Semantic similarity computation failed: %s", e)
            return 0.5
    
    def match_role(self, resume_text: str, resume_skills: List[str], target_role: str) -> Tuple[float, str, List[Dict], List[Dict]]:
        keyword_score = self.calculate_keyword_match(resume_skills, target_role)
        semantic_score = self.calculate_semantic_similarity(resume_text, target_role)
        
        # Semantic drives the verdict; keyword is supporting signal. Calibrate
        # upward slightly to match holistic human/LLM generosity.
        base = (semantic_score * 0.75) + (keyword_score * 0.25)
        calibrated = min(base * 1.12, 1.0)
        final_score = round(calibrated * 10, 1)
        final_score = min(max(final_score, 0), 10)
        
        alt_roles = self._get_alternative_roles(resume_skills, resume_text)
        improvements = self._generate_improvements(resume_skills, target_role, final_score)
        
        final_role = target_role
        for role_name in ROLE_DESCRIPTIONS.keys():
            if role_name.lower() in target_role.lower():
                final_role = role_name
                break
        
        return final_score, final_role, alt_roles, improvements
    
    def _get_alternative_roles(self, skills: List[str], text: str) -> List[Dict]:
        # Prefer real embedding similarity when available; fallback to keyword overlap
        if self.embeddings_model is not None and self.role_embeddings:
            try:
                chunks = self._chunk_text(text, chunk_chars=900, overlap=150)
                chunk_embs = self.embeddings_model.encode(chunks)
                # Use best-chunk similarity per role (same as main scoring)
                scored = []
                for role, role_emb in self.role_embeddings.items():
                    sims = cosine_similarity(chunk_embs, [role_emb]).flatten()
                    scored.append((role, float(max(sims))))
                scored.sort(key=lambda x: x[1], reverse=True)
                return [{"role": r, "match": round(max(0.0, min(s, 1.0)), 2)} for r, s in scored[:3]]
            except Exception as e:
                logger.exception("Alternative roles embedding failed, falling back to keywords: %s", e)

        text_lower = text.lower()
        role_matches = []
        for role, desc in ROLE_DESCRIPTIONS.items():
            keywords = role.lower().split()
            score = sum(1 for kw in keywords if kw in text_lower)
            score += sum(1 for skill in skills if skill.lower() in desc.lower())
            if score > 0:
                role_matches.append((role, score))
        role_matches.sort(key=lambda x: x[1], reverse=True)
        # deterministic but not random: normalize by max score
        max_s = max((s for _, s in role_matches), default=1)
        return [{"role": r, "match": round(s / max_s, 2)} for r, _ in role_matches[:3]]
    
    def _generate_improvements(self, skills: List[str], target_role: str, score: float) -> List[Dict]:
        improvements = []
        skills_lower = [s.lower() for s in skills]
        
        role_requirements = {
            "software engineer": ["project portfolio", "github contributions", "unit testing", "system design"],
            "frontend developer": ["responsive projects", "performance optimization", "accessibility", "state management"],
            "backend developer": ["database design", "api documentation", "security best practices", "caching"],
            "full stack developer": ["deployment experience", "authentication", "rest api", "code reviews"],
            "data scientist": ["kaggle competitions", "data visualization", "statistics", "feature engineering"],
            "machine learning engineer": ["model deployment", "ml ops", "a/b testing", "model optimization"],
            "devops engineer": ["infrastructure as code", "monitoring", "logging", "incident response"],
            "product manager": ["user research", "metrics", "stakeholder management", "product analytics"],
            "ui/ux designer": ["user testing", "design systems", "accessibility", "prototyping"],
            "data analyst": ["sql queries", "dashboard creation", "business metrics", "data cleaning"]
        }
        
        for role_lower, reqs in role_requirements.items():
            if role_lower in target_role.lower():
                missing = [r for r in reqs if not any(r.lower() in s.lower() for s in skills_lower)]
                for item in missing[:3]:
                    priority = "high" if len(improvements) < 2 else "medium"
                    improvements.append({
                        "area": item.title(),
                        "priority": priority
                    })
                break
        
        if not improvements:
            improvements = [
                {"area": "Add quantified achievements", "priority": "high"},
                {"area": "Include relevant certifications", "priority": "medium"},
                {"area": "Detail project outcomes", "priority": "medium"}
            ]
        
        if score >= 8:
            improvements.insert(0, {"area": "Strong match - highlight key achievements", "priority": "high"})
        
        return improvements[:4]