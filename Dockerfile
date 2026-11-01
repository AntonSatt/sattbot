# Discord bot, run as an unprivileged user. The SQLite database lives in
# /app/data, which must be a persistent volume in production: without one,
# every restart wipes the bot's settings.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATABASE_PATH=/app/data/sattbot.db
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin bot \
    && mkdir -p /app/data && chown bot:bot /app/data
COPY . .
USER 10001
CMD ["python", "bot.py"]
