"""
Quiz Generator CLI — Rich command-line interface powered by Click.
"""

import sys
import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .core import (
    generate_quiz,
    parse_response,
    score_quiz,
    export_quiz_json,
    export_quiz_pdf_ready,
    validate_quiz_data,
    check_ollama_running,
    ConfigManager,
    setup_logging,
    QuestionBank,
    QuizResult,
    ScoreTracker,
    TimedQuiz,
    QUIZ_TYPES,
)

console = Console()


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def display_quiz(quiz_data: dict, show_answers: bool = False) -> None:
    """Display the quiz in a rich formatted layout."""
    console.print(
        Panel(
            f"[bold cyan]{quiz_data.get('title', 'Quiz')}[/bold cyan]",
            subtitle=f"Topic: {quiz_data.get('topic', 'N/A')}",
        )
    )

    for q in quiz_data.get("questions", []):
        q_num = q.get("number", "?")
        q_type = q.get("type", "unknown")
        question = q.get("question", "")

        console.print(f"\n[bold yellow]Q{q_num}[/bold yellow] [{q_type}]")
        console.print(f"  {question}")

        if q.get("options"):
            for opt in q["options"]:
                console.print(f"    {opt}")

        if show_answers:
            console.print(f"  [green]Answer: {q.get('answer', 'N/A')}[/green]")
            if q.get("explanation"):
                console.print(f"  [dim]Explanation: {q['explanation']}[/dim]")


def interactive_quiz(quiz_data: dict, timed: bool = False) -> QuizResult:
    """Run the quiz interactively and return a QuizResult."""
    questions = quiz_data.get("questions", [])
    total = len(questions)
    score = 0
    user_answers: list[str] = []

    timer = TimedQuiz(quiz_data) if timed else None
    if timer:
        console.print(
            f"[yellow]⏱  Timer enabled — {timer.time_limit}s total[/yellow]"
        )
        timer.start()

    console.print(
        Panel(
            "[bold green]Interactive Quiz Mode[/bold green]\n"
            "Answer each question. Type your answer and press Enter."
        )
    )

    for q in questions:
        q_num = q.get("number", "?")
        question = q.get("question", "")
        q_type = q.get("type", "unknown")

        console.print(
            f"\n[bold yellow]Question {q_num}/{total}[/bold yellow] [{q_type}]"
        )
        console.print(f"  {question}")

        if q.get("options"):
            for opt in q["options"]:
                console.print(f"    {opt}")

        user_answer = console.input("\n[bold]Your answer: [/bold]").strip()
        user_answers.append(user_answer)
        correct_answer = q.get("answer", "")

        if user_answer.lower() == correct_answer.lower():
            console.print("[green]✓ Correct![/green]")
            score += 1
        else:
            console.print(
                f"[red]✗ Incorrect. The answer is: {correct_answer}[/red]"
            )

        if q.get("explanation"):
            console.print(f"[dim]{q['explanation']}[/dim]")

    if timer:
        timer.stop()

    result = score_quiz(questions, user_answers)
    result.topic = quiz_data.get("topic", "")
    if timer:
        result.time_taken = timer.elapsed

    pct = result.percentage
    color = "green" if pct >= 70 else "yellow" if pct >= 50 else "red"
    console.print(
        Panel(
            f"[bold {color}]Score: {result.score}/{result.total} ({pct:.0f}%)[/bold {color}]",
            title="Results",
        )
    )

    return result


# ---------------------------------------------------------------------------
# CLI group & commands
# ---------------------------------------------------------------------------


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """📝 Quiz Generator — create, take, and manage quizzes with a local LLM."""
    ctx.ensure_object(dict)
    cfg = ConfigManager()
    ctx.obj["config"] = cfg
    log_cfg = cfg.get("logging", default={})
    setup_logging(
        level=log_cfg.get("level", "INFO"),
        log_file=log_cfg.get("file"),
    )


# ---- generate ----


@cli.command()
@click.option("--topic", "-t", required=True, help="Quiz topic")
@click.option("--questions", "-q", default=5, type=int, help="Number of questions")
@click.option(
    "--type",
    "quiz_type",
    type=click.Choice(QUIZ_TYPES),
    default="multiple-choice",
    help="Question type",
)
@click.option(
    "--difficulty",
    "-d",
    type=click.Choice(["easy", "medium", "hard"]),
    default="medium",
    help="Difficulty level",
)
@click.option("--output", "-o", type=click.Path(), help="Save quiz to JSON file")
@click.option("--show-answers", "-a", is_flag=True, help="Show answers immediately")
@click.pass_context
def generate(ctx, topic, questions, quiz_type, difficulty, output, show_answers):
    """Generate a new quiz from a topic."""
    console.print(
        Panel("[bold blue]📝 Quiz Generator[/bold blue]", subtitle="Powered by Local LLM")
    )

    if not check_ollama_running():
        console.print(
            "[red]Error: Ollama is not running. Start with: ollama serve[/red]"
        )
        sys.exit(1)

    console.print(
        f"[cyan]Generating {questions} {quiz_type} questions about '{topic}'...[/cyan]"
    )

    cfg = ctx.obj["config"]
    with console.status("[bold green]Creating quiz..."):
        quiz_data = generate_quiz(
            topic, questions, quiz_type, difficulty, config=cfg
        )

    if output:
        written = export_quiz_json(quiz_data, output)
        console.print(f"[green]Quiz saved to {written}[/green]")

    display_quiz(quiz_data, show_answers=show_answers)


# ---- take ----


@cli.command()
@click.option("--file", "-f", "quiz_file", type=click.Path(exists=True), help="Quiz JSON file")
@click.option("--topic", "-t", help="Generate and take a quiz on this topic")
@click.option("--questions", "-q", default=5, type=int, help="Number of questions (with --topic)")
@click.option("--timer", is_flag=True, help="Enable per-question timer")
@click.pass_context
def take(ctx, quiz_file, topic, questions, timer):
    """Take a quiz interactively."""
    if quiz_file:
        with open(quiz_file, "r", encoding="utf-8") as fh:
            quiz_data = json.load(fh)
    elif topic:
        if not check_ollama_running():
            console.print("[red]Ollama is not running.[/red]")
            sys.exit(1)
        cfg = ctx.obj["config"]
        with console.status("[bold green]Generating quiz..."):
            quiz_data = generate_quiz(topic, questions, config=cfg)
    else:
        console.print("[red]Provide --file or --topic.[/red]")
        sys.exit(1)

    result = interactive_quiz(quiz_data, timed=timer)

    # Record score
    cfg = ctx.obj["config"]
    tracker = ScoreTracker(cfg.get("scoring", "history_file", default="quiz_scores.json"))
    result.topic = quiz_data.get("topic", topic or "")
    tracker.record(result)
    console.print("[dim]Score recorded.[/dim]")


# ---- export ----


@cli.command(name="export")
@click.option("--input", "-i", "input_file", required=True, type=click.Path(exists=True), help="Quiz JSON")
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["json", "markdown", "pdf-ready"]),
    default="json",
    help="Output format",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def export_cmd(input_file, fmt, output):
    """Export a quiz to different formats."""
    with open(input_file, "r", encoding="utf-8") as fh:
        quiz_data = json.load(fh)

    if fmt == "json":
        out_path = output or "quiz_export.json"
        export_quiz_json(quiz_data, out_path)
        console.print(f"[green]Exported JSON → {out_path}[/green]")
    elif fmt in ("markdown", "pdf-ready"):
        md = export_quiz_pdf_ready(quiz_data)
        out_path = output or "quiz_export.md"
        Path(out_path).write_text(md, encoding="utf-8")
        console.print(f"[green]Exported Markdown → {out_path}[/green]")


# ---- bank ----


@cli.group()
@click.pass_context
def bank(ctx):
    """Manage the question bank."""
    cfg = ctx.obj["config"]
    ctx.obj["bank"] = QuestionBank(
        cfg.get("question_bank", "storage_file", default="question_bank.json")
    )


@bank.command(name="add")
@click.option("--file", "-f", "quiz_file", required=True, type=click.Path(exists=True))
@click.pass_context
def bank_add(ctx, quiz_file):
    """Import questions from a quiz JSON file into the bank."""
    with open(quiz_file, "r", encoding="utf-8") as fh:
        quiz_data = json.load(fh)
    qb: QuestionBank = ctx.obj["bank"]
    count = qb.add_from_quiz(quiz_data)
    console.print(f"[green]Added {count} questions to the bank (total: {len(qb)}).[/green]")


@bank.command(name="list")
@click.option("--topic", "-t", default=None, help="Filter by topic")
@click.pass_context
def bank_list(ctx, topic):
    """List questions in the bank."""
    qb: QuestionBank = ctx.obj["bank"]
    questions = qb.filter(topic=topic) if topic else qb.all()
    if not questions:
        console.print("[yellow]Question bank is empty.[/yellow]")
        return
    table = Table(title="Question Bank", show_lines=True)
    table.add_column("#", style="bold")
    table.add_column("Type")
    table.add_column("Question")
    table.add_column("Topic")
    for i, q in enumerate(questions, 1):
        table.add_row(str(i), q.q_type, q.question[:80], q.topic or "—")
    console.print(table)


@bank.command(name="clear")
@click.pass_context
def bank_clear(ctx):
    """Clear all questions from the bank."""
    qb: QuestionBank = ctx.obj["bank"]
    qb.clear()
    console.print("[green]Question bank cleared.[/green]")


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()