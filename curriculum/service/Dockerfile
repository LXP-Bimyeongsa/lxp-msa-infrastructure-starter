FROM python:3.12-slim

WORKDIR /app

COPY curriculum/service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 패키지와 데이터를 함께 넣는다. 카탈로그는 기동할 때 읽는다.
COPY curriculum/ /app/curriculum/

EXPOSE 8086

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8086/actuator/health')"

CMD ["uvicorn", "curriculum.service.app:app", "--host", "0.0.0.0", "--port", "8086"]
