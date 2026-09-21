FROM python:3.9-slim

WORKDIR /app
COPY src ./src
COPY web ./web

ENV PYTHONPATH=/app/src
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/health', timeout=3)"

CMD ["python", "-m", "ss_seo.server"]

