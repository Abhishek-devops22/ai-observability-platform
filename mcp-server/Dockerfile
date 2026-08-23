FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV TRANSPORT=streamable-http \
    HTTP_HOST=0.0.0.0 \
    HTTP_PORT=8080

EXPOSE 8080

USER nobody

CMD ["python", "server.py"]
