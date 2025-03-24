FROM python:3.9-slim

# Installiere kafka-python
RUN pip install kafka-python

WORKDIR /app
COPY segment.py .

CMD ["python", "segment.py"]
