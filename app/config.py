"""All settings in one place. Other files import from here."""
import os
from dotenv import load_dotenv

# Project root = the folder that contains app/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))  # copies .env values into environment variables

# --- AI provider ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("MODEL", "openai/gpt-oss-20b")
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "low")  # low | medium | high
LLM_MAX_WAITS = 4  # how many times we wait + retry after a rate-limit (429) error

# How long each team agent thinks (low | medium | high). More thinking = more tokens + time.
# All start equal to the baseline, so the comparison is fair. Change ONE at a time in Stage 3.
AGENT_EFFORT = {name: REASONING_EFFORT for name in ("planner", "coder", "reviewer", "explainer")}

# Price in USD per 1M tokens: (input, output). From Groq's pricing page.
PRICES = {
    "openai/gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
}

# --- Dataset summary limits (keep prompts small: free plan = 8K tokens/min) ---
MAX_SUMMARY_COLUMNS = 40
SAMPLE_ROWS = 3

# --- Sandbox ---
SANDBOX_TIMEOUT_SEC = 30
SANDBOX_IMAGE = "data-analyst-sandbox:1"
SANDBOX_MEMORY = "512m"
SANDBOX_CPUS = "1"
SANDBOX_MAX_PROCESSES = 128
SANDBOX_MAX_FILE_BYTES = 20_000_000

# --- Web server ---
MAX_UPLOAD_MB = 10
MAX_QUESTION_CHARS = 500
CHART_DIR = os.path.join(ROOT, "charts")
UPLOAD_DIR = os.path.join(ROOT, "uploads")
CHART_MAX_AGE_HOURS = 24  # chart pictures older than this are deleted when the server starts


def require_key():
    """Stop early with a clear message if the key is missing."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing. Copy .env.example to .env and add your key.")
