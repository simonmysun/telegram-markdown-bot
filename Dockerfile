FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --uid 10001 bot

COPY --chown=bot:bot bot.py /app/

USER bot

CMD ["python", "bot.py"]
