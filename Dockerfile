FROM python:3.12-alpine

WORKDIR /app
COPY . /app

EXPOSE 8765

CMD ["python", "server.py", "--no-browser", "--host", "0.0.0.0", "--port", "8765"]
