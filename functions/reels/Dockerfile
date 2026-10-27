# Motore REELS per Hugging Face Spaces (Docker, CPU gratuita). Incolla questo file come "Dockerfile" nel Space.
# Costruisce l'immagine scaricando il codice da GitHub: per aggiornare, nel Space: Settings → Factory rebuild.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git fonts-dejavu-core fonts-inter \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face esegue i container come utente 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1 \
    REELS_DATA_DIR=/home/user/data HF_HOME=/home/user/.cache/huggingface \
    REELS_WHISPER_MODEL=small \
    METODOS_URL=https://quanto-self.vercel.app
WORKDIR /home/user

ARG REPO_BRANCH=claude/reels-video-agent
RUN git clone --depth 1 --branch ${REPO_BRANCH} https://github.com/leonardopanichella08-dotcom/AgenteLP.git src
WORKDIR /home/user/src/functions/reels

RUN pip install --no-cache-dir -r requirements.txt
# Scarica ora i pesi di Whisper (gratis): la prima trascrizione non deve aspettare
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
