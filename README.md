# Quiz Generator

## Features

- AI-powered quiz generation

- Local LLM support using Ollama

- Multiple-choice, true/false, short-answer, and mixed question types

- Adjustable difficulty levels

- Custom number of questions

- Interactive quiz-taking interface

- Automatic score calculation

- Question bank

- Score history and analytics

- Quiz export options

- Professional dark-themed Streamlit dashboard

- Local, privacy-friendly AI inference without a paid AI API

## Tech Stack

- **Python**

- **Streamlit** — Web interface

- **Ollama** — Local LLM runtime

- **Gemma 3** — Default local language model

- **PyYAML** — Configuration management

- **Requests** — Ollama API communication

## Project Structure

```text

quiz-generator/

├── docs/

│   └── images/

├── src/

│   └── quiz_gen/

│       ├── __init__.py

│       ├── core.py

│       ├── cli.py

│       ├── api.py

│       └── web_ui.py

├── common/

│   └── llm_client.py

├── examples/

│   └── demo.py

├── tests/

├── config.yaml

├── requirements.txt

├── setup.py

├── Dockerfile

├── docker-compose.yml

├── Makefile

├── .env.example

├── .gitignore

└── README.md

```

## Requirements

- Python 3.10 or newer

- Git

- Ollama

## Installation

### 1. Clone the repository

```bash

git clone https://github.com/siddiquilaraib527-maker/quiz-generator.git

cd quiz-generator

```

### 2. Create a virtual environment

macOS / Linux:

```bash

python3 -m venv .venv

source .venv/bin/activate

```

Windows:

```bash

python -m venv .venv

.venv\\Scripts\\activate

```

### 3. Install dependencies

```bash

pip install -r requirements.txt

```

If PyYAML is missing:

```bash

pip install pyyaml

```

## Ollama Setup

QuizGen AI uses Ollama to run the language model locally.

Install Ollama from https://ollama.com/.

Pull the Gemma 3 model:

```bash

ollama pull gemma3:4b

```

Verify the model:

```bash

ollama list

```

The default local Ollama API is:

```text

http://localhost:11434

```

## Run the Application

From the project root:

```bash

source .venv/bin/activate

export PYTHONPATH="$PWD/src"

python -m streamlit run src/quiz_gen/web_ui.py

```

The application normally opens at:

```text

http://localhost:8501

```

## How It Works

```text

User

  |

  v

Streamlit Web Interface

  |

  v

Quiz Configuration

  |

  v

Quiz Generator Core

  |

  v

Ollama API

  |

  v

Gemma 3 LLM

  |

  v

Generated Quiz

  |

  +--> Take Quiz

  +--> Calculate Score

  +--> Question Bank

  +--> Score History

```

The user selects a topic, number of questions, question type, and difficulty. The application sends a structured prompt to the local Gemma model through Ollama. The response is parsed and validated before being displayed in the Streamlit interface.

## Example

A user can configure:

```text

Topic: Computer Networks

Questions: 10

Type: Multiple Choice

Difficulty: Medium

```

QuizGen AI then generates an interactive quiz based on those settings.

## Configuration

Project settings can be adjusted through `config.yaml`.

Example:

```yaml

llm:

  temperature: 0.7

  max_tokens: 4096

```

## Troubleshooting

### Ollama is not running

Start Ollama:

```bash

ollama serve

```

Then verify it:

```bash

curl http://localhost:11434/api/tags

```

### Model not found

Check installed models:

```bash

ollama list

```

If `gemma3:4b` is missing:

```bash

ollama pull gemma3:4b

```

### `ModuleNotFoundError: No module named 'quiz_gen'`

From the project root:

```bash

export PYTHONPATH="$PWD/src"

```

Then run:

```bash

python -m streamlit run src/quiz_gen/web_ui.py

```

### Port already in use

Use another port:

```bash

python -m streamlit run src/quiz_gen/web_ui.py --server.port 8502

```

## Running Tests

```bash

pytest

```

## Docker

Build the image:

```bash

docker build -t quizgen-ai .

```

Run the container:

```bash

docker run -p 8501:8501 quizgen-ai

```

If the application runs inside Docker, remember that `localhost` inside the container refers to the container itself. Ollama must therefore be reachable from the container.

## Deployment

QuizGen AI can be deployed to platforms supporting Python or Docker, including Railway.

For cloud deployment, `http://localhost:11434` cannot point to the Ollama installation on your personal computer. A hosted LLM API or separately hosted Ollama instance is required.

## Future Improvements

- User authentication

- Persistent database storage

- Support for additional LLM providers

- PDF and CSV quiz import/export

- AI-generated answer explanations

- Adaptive difficulty

- Teacher/admin dashboard

- Multiplayer quiz mode

- Advanced learning analytics

## License

This project is intended for educational and academic use.

## Author

**Laraib**

GitHub: https://github.com/siddiquilaraib527-maker/quiz-generator

"""

path = Path("/mnt/data/README.md")

path.write_text(readme, encoding="utf-8")

print(path)
