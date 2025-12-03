FROM python:3.13-slim

WORKDIR /app
COPY ./src/requirements.txt /app

RUN pip install --no-cache-dir --upgrade pip \ 
    && pip install --no-cache-dir -r requirements.txt

COPY ./src /app

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]