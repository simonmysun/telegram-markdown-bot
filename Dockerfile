FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --uid 10001 bot

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --requirement requirements.txt

COPY --chown=bot:bot bot.py markdown_converter.py /app/

USER bot

CMD ["python", "bot.py"]
