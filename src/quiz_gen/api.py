"""FastAPI REST API for Quiz Generator."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn

from quiz_gen.core import (
    generate_quiz,
    score_quiz,
    validate_quiz_data,
    export_quiz_pdf_ready,
    QUIZ_TYPES,
)

app = FastAPI(
    title="Quiz Generator API",
    description="REST API for Quiz Generator",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class GenerateQuizRequest(BaseModel):
    topic: str = Field(..., description="Topic for the quiz")
    num_questions: int = Field(5, description="Number of questions to generate")
    quiz_type: str = Field("multiple-choice", description="Type of quiz questions")
    difficulty: str = Field("medium", description="Difficulty level")


class ScoreQuizRequest(BaseModel):
    questions: List[Dict[str, Any]] = Field(..., description="Quiz questions with correct answers")
    user_answers: List[str] = Field(..., description="User-submitted answers")


class ValidateQuizRequest(BaseModel):
    quiz_data: Dict[str, Any] = Field(..., description="Quiz data to validate")


class ExportPdfReadyRequest(BaseModel):
    quiz_data: Dict[str, Any] = Field(..., description="Quiz data to export")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "quiz-generator"}


@app.get("/quiz-types")
async def get_quiz_types():
    """Return the list of supported quiz types."""
    return {"quiz_types": QUIZ_TYPES}


@app.post("/generate")
async def api_generate_quiz(request: GenerateQuizRequest):
    if request.quiz_type not in QUIZ_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid quiz_type '{request.quiz_type}'. Must be one of {QUIZ_TYPES}",
        )
    try:
        result = generate_quiz(
            request.topic,
            request.num_questions,
            request.quiz_type,
            request.difficulty,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/score")
async def api_score_quiz(request: ScoreQuizRequest):
    try:
        result = score_quiz(request.questions, request.user_answers)
        # QuizResult dataclass → convert to dict
        return result if isinstance(result, dict) else result.__dict__
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/validate")
async def api_validate_quiz(request: ValidateQuizRequest):
    try:
        errors = validate_quiz_data(request.quiz_data)
        return {"errors": errors, "valid": len(errors) == 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/export-pdf-ready")
async def api_export_pdf_ready(request: ExportPdfReadyRequest):
    try:
        result = export_quiz_pdf_ready(request.quiz_data)
        return {"content": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)