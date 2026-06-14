# Hugging Face Space (Docker SDK) — runs the full working Demo Capital stack
# in a single container: FastAPI backend (internal :8000) + Streamlit dashboard
# (public :7860). Uses the deterministic mock LLM provider, so no GPU/Ollama needed.
FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl \
 && rm -rf /var/lib/apt/lists/*

# HF Spaces convention: run as non-root uid 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app

# Pull the application source straight from GitHub (stays in sync with the repo).
RUN git clone --depth 1 https://github.com/Vishal-KESHRI/ai-investment-intelligence-platform .

RUN pip install --no-cache-dir --user -r requirements.txt -r dashboard/requirements.txt

COPY --chown=user start.sh /home/user/start.sh
RUN chmod +x /home/user/start.sh

ENV LLM_PROVIDER=mock \
    JWT_SECRET=hf-demo-change-me \
    DATABASE_URL=sqlite:////home/user/app/data/demo.db \
    BACKEND_URL=http://127.0.0.1:8000 \
    STREAMLIT_SERVER_HEADLESS=true

EXPOSE 7860
CMD ["/home/user/start.sh"]
