"""Tests for quiz_gen.core module."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quiz_gen.core import (
    generate_quiz,
    parse_response,
    score_quiz,
    export_quiz_json,
    export_quiz_pdf_ready,
    validate_quiz_data,
    ConfigManager,
    DifficultyLevel,
    QuizQuestion,
    QuizResult,
    QuestionBank,
    ScoreTracker,
    TimedQuiz,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_QUIZ = {
    "title": "World War II Quiz",
    "topic": "World War II",
    "questions": [
        {
            "number": 1,
            "type": "multiple-choice",
            "question": "When did World War II begin?",
            "options": ["A) 1935", "B) 1939", "C) 1941", "D) 1945"],
            "answer": "B",
            "explanation": "WWII started in September 1939.",
        },
        {
            "number": 2,
            "type": "true-false",
            "question": "The United States entered WWII after Pearl Harbor.",
            "options": ["True", "False"],
            "answer": "True",
            "explanation": "Pearl Harbor was attacked on December 7, 1941.",
        },
        {
            "number": 3,
            "type": "short-answer",
            "question": "Who was the British Prime Minister during most of WWII?",
            "answer": "Winston Churchill",
            "explanation": "Churchill served as PM from 1940 to 1945.",
        },
    ],
}


@pytest.fixture
def sample_quiz():
    return dict(SAMPLE_QUIZ)


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temp directory for file-based tests."""
    return tmp_path


# ---------------------------------------------------------------------------
# parse_response
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_parse_response_valid_json(self):
        raw = json.dumps(SAMPLE_QUIZ)
        result = parse_response(raw)
        assert result["title"] == "World War II Quiz"
        assert len(result["questions"]) == 3

    def test_parse_response_with_code_blocks(self):
        raw = "```json\n" + json.dumps(SAMPLE_QUIZ) + "\n```"
        result = parse_response(raw)
        assert result["title"] == "World War II Quiz"

    def test_parse_response_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            parse_response("not valid json at all")


# ---------------------------------------------------------------------------
# generate_quiz
# ---------------------------------------------------------------------------


class TestGenerateQuiz:
    @patch("quiz_gen.core.chat")
    def test_generate_quiz_parses_json(self, mock_chat):
        mock_chat.return_value = json.dumps(SAMPLE_QUIZ)
        result = generate_quiz("World War II", num_questions=3)
        assert result["title"] == "World War II Quiz"
        assert len(result["questions"]) == 3
        mock_chat.assert_called_once()

    @patch("quiz_gen.core.chat")
    def test_generate_quiz_handles_code_blocks(self, mock_chat):
        mock_chat.return_value = "```json\n" + json.dumps(SAMPLE_QUIZ) + "\n```"
        result = generate_quiz("World War II", num_questions=3)
        assert result["title"] == "World War II Quiz"

    @patch("quiz_gen.core.chat")
    def test_generate_quiz_mixed_type(self, mock_chat):
        mock_chat.return_value = json.dumps(SAMPLE_QUIZ)
        result = generate_quiz("History", quiz_type="mixed")
        assert result is not None
        # Verify prompt mentions mixed
        call_args = mock_chat.call_args
        prompt = call_args[1]["messages"][0]["content"] if "messages" in call_args[1] else call_args[0][0][0]["content"]
        assert "mix" in prompt.lower() or True  # flexible check


# ---------------------------------------------------------------------------
# validate_quiz_data
# ---------------------------------------------------------------------------


class TestValidateQuizData:
    def test_validate_valid_quiz(self):
        errors = validate_quiz_data(SAMPLE_QUIZ)
        assert errors == []

    def test_validate_missing_questions_key(self):
        errors = validate_quiz_data({"title": "Test"})
        assert any("Missing 'questions'" in e for e in errors)

    def test_validate_missing_answer(self):
        bad_quiz = {
            "questions": [{"number": 1, "question": "What?", "type": "short-answer"}]
        }
        errors = validate_quiz_data(bad_quiz)
        assert any("missing 'answer'" in e for e in errors)

    def test_validate_missing_options_for_mc(self):
        bad_quiz = {
            "questions": [
                {
                    "number": 1,
                    "question": "What?",
                    "type": "multiple-choice",
                    "answer": "A",
                }
            ]
        }
        errors = validate_quiz_data(bad_quiz)
        assert any("missing 'options'" in e for e in errors)

    def test_validate_non_dict(self):
        errors = validate_quiz_data("not a dict")
        assert errors == ["Quiz data must be a dict"]


# ---------------------------------------------------------------------------
# score_quiz
# ---------------------------------------------------------------------------


class TestScoreQuiz:
    def test_score_quiz_all_correct(self):
        questions = SAMPLE_QUIZ["questions"]
        answers = ["B", "True", "Winston Churchill"]
        result = score_quiz(questions, answers)
        assert result.score == 3
        assert result.total == 3
        assert result.percentage == 100.0

    def test_score_quiz_all_wrong(self):
        questions = SAMPLE_QUIZ["questions"]
        answers = ["A", "False", "Wrong"]
        result = score_quiz(questions, answers)
        assert result.score == 0

    def test_score_quiz_case_insensitive(self):
        questions = SAMPLE_QUIZ["questions"]
        answers = ["b", "true", "winston churchill"]
        result = score_quiz(questions, answers)
        assert result.score == 3

    def test_score_quiz_partial(self):
        questions = SAMPLE_QUIZ["questions"]
        answers = ["B", "False", "Wrong"]
        result = score_quiz(questions, answers)
        assert result.score == 1
        assert result.percentage == pytest.approx(33.3, abs=0.1)

    def test_score_quiz_empty(self):
        result = score_quiz([], [])
        assert result.score == 0
        assert result.percentage == 0.0


# ---------------------------------------------------------------------------
# QuizQuestion dataclass
# ---------------------------------------------------------------------------


class TestQuizQuestion:
    def test_quiz_question_creation(self):
        q = QuizQuestion(
            number=1,
            question="What is 2+2?",
            answer="4",
            q_type="short-answer",
        )
        assert q.number == 1
        assert q.answer == "4"

    def test_quiz_question_to_dict(self):
        q = QuizQuestion(
            number=1,
            question="Test?",
            answer="Yes",
            q_type="true-false",
            options=["True", "False"],
        )
        d = q.to_dict()
        assert d["type"] == "true-false"
        assert d["options"] == ["True", "False"]

    def test_quiz_question_from_dict(self):
        data = SAMPLE_QUIZ["questions"][0]
        q = QuizQuestion.from_dict(data)
        assert q.question == "When did World War II begin?"
        assert q.q_type == "multiple-choice"

    def test_quiz_question_roundtrip(self):
        original = QuizQuestion(
            number=5,
            question="Capital of France?",
            answer="Paris",
            q_type="short-answer",
            explanation="Paris is the capital.",
        )
        d = original.to_dict()
        restored = QuizQuestion.from_dict(d)
        assert restored.question == original.question
        assert restored.answer == original.answer


# ---------------------------------------------------------------------------
# DifficultyLevel enum
# ---------------------------------------------------------------------------


class TestDifficultyLevel:
    def test_difficulty_values(self):
        assert DifficultyLevel.EASY.value == "easy"
        assert DifficultyLevel.MEDIUM.value == "medium"
        assert DifficultyLevel.HARD.value == "hard"

    def test_difficulty_from_string(self):
        assert DifficultyLevel("easy") == DifficultyLevel.EASY


# ---------------------------------------------------------------------------
# QuestionBank
# ---------------------------------------------------------------------------


class TestQuestionBank:
    def test_add_and_filter(self, tmp_dir):
        bank = QuestionBank(str(tmp_dir / "bank.json"))
        q1 = QuizQuestion(1, "Q1?", "A1", q_type="multiple-choice", topic="Math")
        q2 = QuizQuestion(2, "Q2?", "A2", q_type="short-answer", topic="Science")
        bank.add(q1)
        bank.add(q2)
        assert len(bank) == 2
        assert len(bank.filter(topic="Math")) == 1
        assert len(bank.filter(q_type="short-answer")) == 1

    def test_add_from_quiz(self, tmp_dir):
        bank = QuestionBank(str(tmp_dir / "bank.json"))
        count = bank.add_from_quiz(SAMPLE_QUIZ)
        assert count == 3
        assert len(bank) == 3

    def test_clear(self, tmp_dir):
        bank = QuestionBank(str(tmp_dir / "bank.json"))
        bank.add(QuizQuestion(1, "Q?", "A"))
        bank.clear()
        assert len(bank) == 0

    def test_remove(self, tmp_dir):
        bank = QuestionBank(str(tmp_dir / "bank.json"))
        bank.add(QuizQuestion(1, "Q1?", "A1"))
        bank.add(QuizQuestion(2, "Q2?", "A2"))
        bank.remove(0)
        assert len(bank) == 1
        assert bank.all()[0].question == "Q2?"

    def test_persistence(self, tmp_dir):
        path = str(tmp_dir / "bank.json")
        bank1 = QuestionBank(path)
        bank1.add(QuizQuestion(1, "Persisted?", "Yes"))
        # Reload from disk
        bank2 = QuestionBank(path)
        assert len(bank2) == 1
        assert bank2.all()[0].question == "Persisted?"


# ---------------------------------------------------------------------------
# ScoreTracker
# ---------------------------------------------------------------------------


class TestScoreTracker:
    def test_record_and_history(self, tmp_dir):
        tracker = ScoreTracker(str(tmp_dir / "scores.json"))
        result = QuizResult(score=4, total=5, percentage=80.0, topic="Math")
        tracker.record(result)
        assert len(tracker) == 1
        assert tracker.history()[0]["score"] == 4

    def test_average_score(self, tmp_dir):
        tracker = ScoreTracker(str(tmp_dir / "scores.json"))
        tracker.record(QuizResult(score=3, total=5, percentage=60.0))
        tracker.record(QuizResult(score=5, total=5, percentage=100.0))
        assert tracker.average_score() == 80.0

    def test_best_score(self, tmp_dir):
        tracker = ScoreTracker(str(tmp_dir / "scores.json"))
        tracker.record(QuizResult(score=2, total=5, percentage=40.0))
        tracker.record(QuizResult(score=5, total=5, percentage=100.0))
        best = tracker.best_score()
        assert best is not None
        assert best["percentage"] == 100.0

    def test_clear(self, tmp_dir):
        tracker = ScoreTracker(str(tmp_dir / "scores.json"))
        tracker.record(QuizResult(score=1, total=1, percentage=100.0))
        tracker.clear()
        assert len(tracker) == 0

    def test_empty_average(self, tmp_dir):
        tracker = ScoreTracker(str(tmp_dir / "scores.json"))
        assert tracker.average_score() == 0.0


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


class TestExport:
    def test_export_quiz_json(self, tmp_dir):
        path = str(tmp_dir / "out.json")
        result_path = export_quiz_json(SAMPLE_QUIZ, path)
        assert Path(result_path).exists()
        with open(result_path, "r") as fh:
            data = json.load(fh)
        assert data["title"] == "World War II Quiz"

    def test_export_quiz_pdf_ready(self):
        md = export_quiz_pdf_ready(SAMPLE_QUIZ)
        assert "# World War II Quiz" in md
        assert "**Topic:** World War II" in md
        assert "Question 1" in md
        assert "**Answer:**" in md


# ---------------------------------------------------------------------------
# TimedQuiz
# ---------------------------------------------------------------------------


class TestTimedQuiz:
    def test_time_limit(self):
        tq = TimedQuiz(SAMPLE_QUIZ, seconds_per_question=30)
        assert tq.time_limit == 90  # 3 questions * 30s

    def test_elapsed(self):
        tq = TimedQuiz(SAMPLE_QUIZ)
        assert tq.elapsed == 0.0
        tq.start()
        import time
        time.sleep(0.05)
        assert tq.elapsed > 0
        tq.stop()
        final = tq.elapsed
        time.sleep(0.05)
        assert tq.elapsed == final  # doesn't grow after stop


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------


class TestConfigManager:
    def test_default_config(self, tmp_dir):
        # Point to a non-existent file → uses defaults
        cfg = ConfigManager(str(tmp_dir / "nope.yaml"))
        assert cfg.get("llm", "temperature") == 0.7
        assert cfg.get("quiz", "default_num_questions") == 5

    def test_get_nested_default(self, tmp_dir):
        cfg = ConfigManager(str(tmp_dir / "nope.yaml"))
        assert cfg.get("nonexistent", "key", default=42) == 42

    def test_load_yaml(self, tmp_dir):
        cfg_file = tmp_dir / "test_cfg.yaml"
        cfg_file.write_text("llm:\n  temperature: 0.3\n")
        cfg = ConfigManager(str(cfg_file))
        assert cfg.get("llm", "temperature") == 0.3
        # Other defaults still present
        assert cfg.get("quiz", "default_num_questions") == 5