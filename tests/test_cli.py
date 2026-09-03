"""Tests for quiz_gen.cli module."""

import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quiz_gen.cli import cli

SAMPLE_QUIZ = {
    "title": "Test Quiz",
    "topic": "Testing",
    "questions": [
        {
            "number": 1,
            "type": "multiple-choice",
            "question": "What is 2+2?",
            "options": ["A) 3", "B) 4", "C) 5", "D) 6"],
            "answer": "B",
            "explanation": "Basic arithmetic.",
        }
    ],
}


class TestCLIGenerate:
    @patch("quiz_gen.cli.check_ollama_running", return_value=True)
    @patch("quiz_gen.cli.generate_quiz", return_value=SAMPLE_QUIZ)
    def test_cli_generate_basic(self, mock_gen, mock_ollama):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--topic", "Math"])
        assert result.exit_code == 0
        assert "Quiz Generator" in result.output

    @patch("quiz_gen.cli.check_ollama_running", return_value=True)
    @patch("quiz_gen.cli.generate_quiz", return_value=SAMPLE_QUIZ)
    def test_cli_generate_with_output(self, mock_gen, mock_ollama, tmp_path):
        runner = CliRunner()
        out_file = str(tmp_path / "quiz.json")
        result = runner.invoke(cli, ["generate", "--topic", "Math", "--output", out_file])
        assert result.exit_code == 0
        assert os.path.exists(out_file)
        with open(out_file) as fh:
            data = json.load(fh)
        assert data["title"] == "Test Quiz"

    @patch("quiz_gen.cli.check_ollama_running", return_value=False)
    def test_cli_ollama_not_running(self, mock_ollama):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--topic", "Math"])
        assert result.exit_code != 0
        assert "not running" in result.output.lower() or "ollama" in result.output.lower()


class TestCLIExport:
    def test_cli_export_json(self, tmp_path):
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(SAMPLE_QUIZ))
        out_file = str(tmp_path / "exported.json")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["export", "--input", str(input_file), "--format", "json", "--output", out_file]
        )
        assert result.exit_code == 0
        assert os.path.exists(out_file)

    def test_cli_export_markdown(self, tmp_path):
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(SAMPLE_QUIZ))
        out_file = str(tmp_path / "exported.md")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["export", "--input", str(input_file), "--format", "markdown", "--output", out_file]
        )
        assert result.exit_code == 0
        assert os.path.exists(out_file)


class TestCLIHelp:
    def test_cli_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Quiz Generator" in result.output

    def test_generate_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--topic" in result.output