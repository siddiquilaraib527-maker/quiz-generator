
from rag.retriever import Retriever
from common.llm_client import chat
import json
import re


MODEL_NAME = "gemma3:4b"
MIN_RELEVANCE_SCORE = 0.20


def clean_json_response(response: str):
    """Extract and parse a JSON object from the model response."""
    response = response.strip()

    response = re.sub(
        r"^```(?:json)?\s*",
        "",
        response,
        flags=re.IGNORECASE
    )
    response = re.sub(r"\s*```$", "", response)

    start = response.find("{")
    end = response.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("The model did not return valid JSON.")

    return json.loads(response[start:end + 1])


def ask_model(prompt: str, max_tokens: int = 5000):
    """Call Ollama using the existing chat client."""
    response = chat(
        [{"role": "user", "content": prompt}],
        model=MODEL_NAME,
        temperature=0.0,
        max_tokens=max_tokens
    )
    return clean_json_response(response)


def validate_quiz_structure(quiz, num_questions: int):
    """Check the basic structure of the generated quiz."""

    if not isinstance(quiz, dict):
        raise ValueError("Invalid quiz format.")

    questions = quiz.get("questions")

    if not isinstance(questions, list):
        raise ValueError("The quiz has no valid questions list.")

    if len(questions) != num_questions:
        raise ValueError(
            f"Expected {num_questions} questions, "
            f"but received {len(questions)}."
        )

    for number, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            raise ValueError(f"Question {number} has an invalid format.")

        if not isinstance(question.get("question"), str):
            raise ValueError(f"Question {number} has no question text.")

        if not question["question"].strip():
            raise ValueError(f"Question {number} is empty.")

        options = question.get("options")

        if not isinstance(options, list) or len(options) != 4:
            raise ValueError(
                f"Question {number} must have exactly four options."
            )

        if not all(isinstance(option, str) and option.strip()
                   for option in options):
            raise ValueError(
                f"Question {number} contains an empty option."
            )

        if question.get("answer") not in ["A", "B", "C", "D"]:
            raise ValueError(
                f"Question {number} has an invalid answer."
            )

        question["number"] = number
        question["type"] = "multiple-choice"

    return quiz


def generate_questions(topic: str, context: str, num_questions: int):
    """Generate MCQs using only the retrieved PDF context."""

    prompt = f"""
You are generating a quiz strictly from an uploaded PDF.

TOPIC:
{json.dumps(topic)}

SOURCE CONTEXT:
<context>
{context}
</context>

STRICT RULES:
1. Use only information supported by the source context.
2. Every question must test information relevant to the topic.
3. The correct answer must be directly supported by the context.
4. Never invent facts or use outside knowledge.
5. Do not create questions about facts absent from the context.
6. All four options must be relevant to the topic.
7. Exactly one option must be correct.
8. Do not make an unsupported option the correct answer.
9. If the context cannot support enough questions, do not invent them.
10. Return exactly {num_questions} questions only if all can be
    supported by the context.
11. Return only valid JSON without markdown.

Required JSON:
{{
  "title": "Quiz",
  "topic": {json.dumps(topic)},
  "questions": [
    {{
      "number": 1,
      "type": "multiple-choice",
      "question": "Question text",
      "options": [
        "A) Option 1",
        "B) Option 2",
        "C) Option 3",
        "D) Option 4"
      ],
      "answer": "A"
    }}
  ]
}}
"""

    return ask_model(prompt)


def verify_quiz(quiz, context: str):
    """
    Ask the model to verify each question and its correct answer
    against the source context. Any uncertain item fails.
    """

    prompt = f"""
You are a strict source-grounding verifier.

SOURCE CONTEXT:
<context>
{context}
</context>

QUIZ TO VERIFY:
{json.dumps(quiz, ensure_ascii=False)}

For every question:
1. Check whether its topic is relevant to the source.
2. Check whether the question can be answered from the source.
3. Check whether the marked correct answer is explicitly supported
   by the source context.
4. Check whether the marked answer is actually correct according
   to the source.
5. Check whether the question contains invented or unsupported facts.

Mark a question supported=true ONLY when the source provides enough
evidence for its question and correct answer.
If uncertain, mark supported=false.
Do not use outside knowledge.

Return only valid JSON in this format:
{{
  "results": [
    {{
      "number": 1,
      "supported": true,
      "reason": "Brief evidence-based reason"
    }}
  ]
}}

Include one result for every question. Do not omit questions.
"""

    result = ask_model(prompt, max_tokens=2500)
    verdicts = result.get("results")

    if not isinstance(verdicts, list):
        raise ValueError("The source verification returned invalid data.")

    expected_count = len(quiz["questions"])

    if len(verdicts) != expected_count:
        raise ValueError(
            "Could not verify every question. "
            "Please try generating the quiz again."
        )

    # Fail closed: missing, malformed or false verdicts reject the quiz.
    for number, verdict in enumerate(verdicts, start=1):
        if not isinstance(verdict, dict):
            raise ValueError("Invalid verification result.")

        if verdict.get("number") != number:
            raise ValueError("Question verification numbers do not match.")

        if verdict.get("supported") is not True:
            reason = verdict.get(
                "reason",
                "The PDF does not sufficiently support this question."
            )
            return False, number, reason

    return True, None, None


def generate_rag_quiz(topic: str, num_questions: int = 15):
    """Generate, verify and return a PDF-grounded quiz."""

    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("Please enter a topic.")

    if not isinstance(num_questions, int) or not 1 <= num_questions <= 30:
        raise ValueError("Choose between 1 and 30 questions.")

    topic = topic.strip()
    retriever = Retriever()

    # Retrieve source content for the requested topic.
    results = retriever.search(topic, top_k=5)

    if not results:
        raise ValueError(
            "This topic is not covered in the uploaded PDF."
        )

    best_score = results[0]["score"]
    print(f"Best relevance score: {best_score:.4f}")

    if best_score < MIN_RELEVANCE_SCORE:
        raise ValueError(
            "This topic does not appear to be covered in the uploaded PDF."
        )

    context = "\n\n".join(
        item["text"] for item in results
    )

    last_reason = ""

    # Try at most twice; never return an unverified quiz.
    for attempt in range(2):
        try:
            quiz = generate_questions(
                topic,
                context,
                num_questions
            )

            quiz = validate_quiz_structure(
                quiz,
                num_questions
            )

            is_supported, bad_number, reason = verify_quiz(
                quiz,
                context
            )

            if is_supported:
                print("All questions passed source verification.")
                return quiz

            last_reason = (
                f"Question {bad_number} failed source verification: "
                f"{reason}"
            )
            print(last_reason)

        except (ValueError, json.JSONDecodeError) as error:
            last_reason = str(error)
            print(f"Generation/verification attempt failed: {error}")

        if attempt == 0:
            print("Retrying quiz generation and verification...")

    raise ValueError(
        "A fully PDF-supported quiz could not be verified. "
        "Try fewer questions or a more specific topic. "
        f"Details: {last_reason}"
    )


if __name__ == "__main__":
    try:
        quiz = generate_rag_quiz("OSI Model", 5)

        print("\nVerified RAG Quiz:\n")
        print(json.dumps(quiz, indent=2, ensure_ascii=False))

    except (ValueError, FileNotFoundError) as error:
        print(f"\nUnable to generate quiz: {error}")
