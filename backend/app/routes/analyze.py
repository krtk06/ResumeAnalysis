from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import logging
import traceback

from ..services.resume_parser import ResumeParser
from ..services.nlp_analyzer import NLPAnalyzer
from ..services.matcher import RoleMatcher, ROLE_DESCRIPTIONS
from ..services.llm_scorer import score_with_openai

logger = logging.getLogger(__name__)

router = APIRouter()

nlp_analyzer = NLPAnalyzer()
role_matcher = RoleMatcher()

@router.post("/analyze")
async def analyze_resume(
    file: UploadFile = File(...),
    target_role: str = Form(...)
):
    try:
        file_bytes = await file.read()
        
        file_size = len(file_bytes)
        if file_size > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Maximum 10MB allowed.")
        
        allowed_extensions = ['pdf', 'doc', 'docx']
        file_ext = file.filename.lower().split('.')[-1]
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}")
        
        text = ResumeParser.parse(file_bytes, file.filename)
        text = ResumeParser.clean_text(text)
        
        if len(text) < 50:
            raise HTTPException(status_code=400, detail="Resume text too short. Please upload a complete resume.")
        
        extracted = nlp_analyzer.analyze(text)
        
        # Local Tier 1 scoring (always computed as fallback + for alt_roles if LLM omits them)
        local_score, matched_role, local_alt_roles, local_improvements = role_matcher.match_role(
            text, extracted["skills"], target_role
        )

        # Try OpenAI (gpt-4o-mini) when key is set; fallback to local
        llm_result = None
        try:
            role_desc = ROLE_DESCRIPTIONS.get(matched_role, ROLE_DESCRIPTIONS.get(target_role, target_role))
            llm_result = score_with_openai(text, target_role, extracted["skills"], role_desc)
        except Exception as e:
            logger.warning("LLM scorer invocation failed, using local score: %s", e)

        if llm_result is not None:
            llm_score, _llm_label, llm_alt_roles, llm_improvements, is_resume = llm_result
            if not is_resume:
                raise HTTPException(status_code=400, detail="Uploaded document is not a valid resume. Please upload a candidate resume with experience and education.")
            score = llm_score
            # Prefer LLM alt_roles/improvements when provided, else keep local
            alt_roles = llm_alt_roles if llm_alt_roles else local_alt_roles
            improvements = llm_improvements if llm_improvements else local_improvements
            scoring_source = "openai"
        else:
            # Local fallback: heuristic reject for obvious non-resumes (e.g. project specs)
            text_lower = text.lower()
            non_resume_signals = ["scope of work", "deliverables", "evaluation focus", "llm usage guidance"]
            if any(s in text_lower for s in non_resume_signals) and len(extracted["skills"]) <= 2:
                raise HTTPException(status_code=400, detail="Uploaded document is not a valid resume. Please upload a candidate resume with experience and education.")
            score, alt_roles, improvements = local_score, local_alt_roles, local_improvements
            scoring_source = "local"
        
        return JSONResponse(content={
            "score": score,
            "matched_role": matched_role,
            "alternative_roles": alt_roles,
            "improvements": improvements,
            "extracted_entities": extracted,
            "scoring_source": scoring_source,
        })
    
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"Analysis failed: {str(e)}"
        logger.error("%s\n%s", error_detail, traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_detail)

@router.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@router.get("/roles")
async def get_roles():
    return {
        "roles": [
            "Software Engineer",
            "Frontend Developer",
            "Backend Developer",
            "Full Stack Developer",
            "Data Scientist",
            "Machine Learning Engineer",
            "DevOps Engineer",
            "Product Manager",
            "UI/UX Designer",
            "Data Analyst"
        ]
    }