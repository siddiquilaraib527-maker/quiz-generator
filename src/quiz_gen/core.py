"""
Quiz Generator Core — Business logic for quiz generation, scoring, and management.
"""

import sys
import os
import json
import logging
import time
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml

# Preserve the original LLM import pattern
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from common.llm_client import chat, check_ollama_running  # noqa: E402

logger = logging.getLogger("quiz_gen")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

QUIZ_TYPES = ["multiple-choice", "true-false", "short-answer", "mixed"]

SYSTEM_PROMPT = """You are an expert quiz creator. Generate quizzes in valid JSON format.

Return a JSON object with this structure:
{
  "title": "Quiz Title",
  "topic": "Topic Name",
  "questions": [
    {
      "number": 1,
      "type": "multiple-choice",
      "question": "What is ...?",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "answer": "A",
      "explanation": "Brief explanation"
    }
  ]
}

For true-false questions, options should be ["True", "False"] and answer should be "True" or "False".
For short-answer questions, omit the options field.
Return ONLY the JSON, no other text."""

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "llm": {"temperature": 0.7, "max_tokens": 4096},
    "quiz": {
        "default_num_questions": 5,
        "default_type": "multiple-choice",
        "default_difficulty": "medium",
        "supported_types": QUIZ_TYPES,
        "max_questions": 50,
    },
    "timer": {"enabled": False, "default_seconds_per_question": 30},
    "scoring": {"history_file": "quiz_scores.json"},
    "question_bank": {"storage_file": "question_bank.json"},
    "export": {"default_format": "json"},
    "logging": {"level": "INFO", "file": "quiz_gen.log"},
}


class ConfigManager:
    """Loads and provides access to config.yaml with sensible defaults."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Initialize the instance."""
        self._config = dict(_DEFAULT_CONFIG)
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "config.yaml"
            )
        self._path = config_path
        self._load()

    def _load(self) -> None:
        """Load data from storage."""
        path = Path(self._path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as fh:
                user_cfg = yaml.safe_load(fh) or {}
            self._merge(self._config, user_cfg)

    @staticmethod
    def _merge(base: dict, override: dict) -> None:
        """Merge override values into base."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigManager._merge(base[key], value)
            else:
                base[key] = value

    def get(self, *keys: Any, default: Optional[Any]=None) -> Any:
        """Retrieve a nested config value, e.g. cfg.get('llm', 'temperature')."""
        node = self._config
        for k in keys:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                return default
        return node

    @property
    def raw(self) -> dict:
        """Return the raw underlying data."""
        return self._config


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """Configure the quiz_gen logger."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
    logger.setLevel(numeric)


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------


class DifficultyLevel(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class QuizQuestion:
    number: int
    question: str
    answer: str
    q_type: str = "multiple-choice"
    options: Optional[list[str]] = None
    explanation: Optional[str] = None
    topic: Optional[str] = None
    difficulty: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        d: dict = {
            "number": self.number,
            "type": self.q_type,
            "question": self.question,
            "answer": self.answer,
        }
        if self.options:
            d["options"] = self.options
        if self.explanation:
            d["explanation"] = self.explanation
        if self.topic:
            d["topic"] = self.topic
        if self.difficulty:
            d["difficulty"] = self.difficulty
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "QuizQuestion":
        """Create instance from dictionary data."""
        return cls(
            number=data.get("number", 0),
            question=data.get("question", ""),
            answer=data.get("answer", ""),
            q_type=data.get("type", "multiple-choice"),
            options=data.get("options"),
            explanation=data.get("explanation"),
            topic=data.get("topic"),
            difficulty=data.get("difficulty"),
        )


@dataclass
class QuizResult:
    score: int
    total: int
    percentage: float
    time_taken: float = 0.0
    topic: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "QuizResult":
        """Create instance from dictionary data."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_response(text: str) -> dict:
    """Parse LLM response text into a quiz dict, handling code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


# ---------------------------------------------------------------------------
# Quiz validation
# ---------------------------------------------------------------------------


def validate_quiz_data(quiz_data: dict) -> list[str]:
    """Return a list of validation errors (empty == valid)."""
    errors: list[str] = []
    if not isinstance(quiz_data, dict):
        return ["Quiz data must be a dict"]
    if "questions" not in quiz_data:
        errors.append("Missing 'questions' key")
        return errors
    if not isinstance(quiz_data["questions"], list):
        errors.append("'questions' must be a list")
        return errors
    for i, q in enumerate(quiz_data["questions"]):
        if not q.get("question"):
            errors.append(f"Question {i + 1}: missing 'question' text")
        if not q.get("answer"):
            errors.append(f"Question {i + 1}: missing 'answer'")
        if q.get("type") in ("multiple-choice", "true-false") and not q.get("options"):
            errors.append(f"Question {i + 1}: missing 'options' for {q.get('type')}")
    return errors


# ---------------------------------------------------------------------------
# Quiz generation
# ---------------------------------------------------------------------------


def generate_quiz(
    topic: str,
    num_questions: int = 5,
    quiz_type: str = "multiple-choice",
    difficulty: str = "medium",
    config: Optional[ConfigManager] = None,
) -> dict:
    """Generate a quiz using the LLM."""
    cfg = config or ConfigManager()
    temperature = cfg.get("llm", "temperature", default=0.3)
    max_tokens = cfg.get("llm", "max_tokens", default=2048)

    if quiz_type == "mixed":
        type_instruction = (
            "Use a mix of multiple-choice, true/false, and short-answer questions."
        )
    else:
        type_instruction = f"All questions should be {quiz_type} format."

    prompt = (
        f"Create a quiz about '{topic}' with exactly {num_questions} questions.\n"
        f"Difficulty level: {difficulty}.\n"
        f"{type_instruction}\n"
        f"Make questions educational and engaging."
    )

    logger.info("Generating quiz: topic=%s, n=%d, type=%s, diff=%s",
                topic, num_questions, quiz_type, difficulty)

    response = chat(
        messages=[{"role": "user", "content": prompt}],
        system_prompt=SYSTEM_PROMPT,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    quiz_data = parse_response(response)
    errors = validate_quiz_data(quiz_data)
    if errors:
        logger.warning("Quiz validation issues: %s", errors)

    return quiz_data


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_quiz(questions: list[dict], user_answers: list[str]) -> QuizResult:
    """Score user answers against the quiz and return a QuizResult."""
    correct = 0
    total = len(questions)
    for q, ua in zip(questions, user_answers):
        if ua.strip().lower() == q.get("answer", "").strip().lower():
            correct += 1
    pct = (correct / total * 100) if total > 0 else 0.0
    return QuizResult(score=correct, total=total, percentage=round(pct, 1))


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def export_quiz_json(quiz_data: dict, path: str) -> str:
    """Export quiz to a JSON file. Returns the absolute path written."""
    out = Path(path)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(quiz_data, fh, indent=2, ensure_ascii=False)
    return str(out.resolve())


def export_quiz_pdf_ready(quiz_data: dict) -> str:
    """Generate Markdown formatted for PDF conversion."""
    lines: list[str] = []
    title = quiz_data.get("title", "Quiz")
    topic = quiz_data.get("topic", "")
    lines.append(f"# {title}")
    if topic:
        lines.append(f"\n**Topic:** {topic}\n")
    lines.append("---\n")

    for q in quiz_data.get("questions", []):
        num = q.get("number", "?")
        lines.append(f"## Question {num} ({q.get('type', '')})\n")
        lines.append(f"{q.get('question', '')}\n")
        if q.get("options"):
            for opt in q["options"]:
                lines.append(f"- {opt}")
            lines.append("")
        lines.append(f"**Answer:** {q.get('answer', 'N/A')}\n")
        if q.get("explanation"):
            lines.append(f"*{q['explanation']}*\n")
        lines.append("---\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Question Bank
# ---------------------------------------------------------------------------


class QuestionBank:
    """Manages a persistent bank of quiz questions."""

    def __init__(self, storage_file: str = "question_bank.json") -> None:
        """Initialize the instance."""
        self._path = Path(storage_file)
        self._questions: list[QuizQuestion] = []
        self._load()

    def _load(self) -> None:
        """Load data from storage."""
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._questions = [QuizQuestion.from_dict(q) for q in data]

    def _save(self) -> None:
        """Save data to storage."""
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump([q.to_dict() for q in self._questions], fh, indent=2)

    def add(self, question: QuizQuestion) -> None:
        """Add."""
        self._questions.append(question)
        self._save()

    def add_from_quiz(self, quiz_data: dict) -> int:
        """Import all questions from a quiz dict. Returns count added."""
        added = 0
        topic = quiz_data.get("topic", "")
        for q in quiz_data.get("questions", []):
            qq = QuizQuestion.from_dict(q)
            qq.topic = qq.topic or topic
            self._questions.append(qq)
            added += 1
        self._save()
        return added

    def remove(self, index: int) -> None:
        """Remove."""
        if 0 <= index < len(self._questions):
            self._questions.pop(index)
            self._save()

    def filter(
        self,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        q_type: Optional[str] = None,
    ) -> list[QuizQuestion]:
        """Filter."""
        results = self._questions
        if topic:
            results = [q for q in results if q.topic and topic.lower() in q.topic.lower()]
        if difficulty:
            results = [q for q in results if q.difficulty == difficulty]
        if q_type:
            results = [q for q in results if q.q_type == q_type]
        return results

    def all(self) -> list[QuizQuestion]:
        """All."""
        return list(self._questions)

    def clear(self) -> None:
        """Clear."""
        self._questions.clear()
        self._save()

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self._questions)


# ---------------------------------------------------------------------------
# Timed Quiz
# ---------------------------------------------------------------------------


class TimedQuiz:
    """Wraps a quiz with timer functionality."""

    def __init__(self, quiz_data: dict, seconds_per_question: int = 30) -> None:
        """Initialize the instance."""
        self.quiz_data = quiz_data
        self.seconds_per_question = seconds_per_question
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    def start(self) -> None:
        """Start."""
        self._start_time = time.time()

    def stop(self) -> None:
        """Stop."""
        self._end_time = time.time()

    @property
    def elapsed(self) -> float:
        """Elapsed."""
        if self._start_time is None:
            return 0.0
        end = self._end_time or time.time()
        return round(end - self._start_time, 1)

    @property
    def time_limit(self) -> int:
        """Time limit."""
        n = len(self.quiz_data.get("questions", []))
        return n * self.seconds_per_question

    @property
    def is_expired(self) -> bool:
        """Is expired."""
        return self.elapsed > self.time_limit


# ---------------------------------------------------------------------------
# Score Tracker
# ---------------------------------------------------------------------------


class ScoreTracker:
    """Tracks quiz scores across sessions, persisted to JSON."""

    def __init__(self, history_file: str = "quiz_scores.json") -> None:
        """Initialize the instance."""
        self._path = Path(history_file)
        self._scores: list[dict] = []
        self._load()

    def _load(self) -> None:
        """Load data from storage."""
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as fh:
                self._scores = json.load(fh)

    def _save(self) -> None:
        """Save data to storage."""
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(self._scores, fh, indent=2)

    def record(self, result: QuizResult) -> None:
        """Record."""
        entry = result.to_dict()
        if not entry.get("timestamp"):
            entry["timestamp"] = datetime.now().isoformat()
        self._scores.append(entry)
        self._save()

    def history(self) -> list[dict]:
        """History."""
        return list(self._scores)

    def average_score(self) -> float:
        """Average score."""
        if not self._scores:
            return 0.0
        return round(
            sum(s.get("percentage", 0) for s in self._scores) / len(self._scores), 1
        )

    def best_score(self) -> Optional[dict]:
        """Best score."""
        if not self._scores:
            return None
        return max(self._scores, key=lambda s: s.get("percentage", 0))

    def clear(self) -> None:
        """Clear."""
        self._scores.clear()
        self._save()

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self._scores)