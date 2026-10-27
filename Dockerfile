FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY src src
RUN pip install --no-cache-dir ".[postgres]"
RUN useradd --create-home --uid 10001 analyst && mkdir -p /app/data /app/reports && chown analyst:analyst /app/data /app/reports
USER analyst
ENTRYPOINT ["olist-logistics"]
CMD ["run", "--with-postgres"]
