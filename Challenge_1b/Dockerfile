FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY main.py .

COPY ["Collection 1/", "./Collection 1/"]
COPY ["Collection 2/", "./Collection 2/"]
COPY ["Collection 3/", "./Collection 3/"]

ENTRYPOINT ["python", "main.py"]