FROM python:3.12-slim

WORKDIR /app

COPY curriculum/service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 가져갈 것만 적는다. 레포에 .dockerignore 가 없어서 curriculum/ 을 통째로
# 복사하면 로컬 .venv 나 __pycache__ 까지 이미지에 들어간다.
# 루트에 .dockerignore 를 두면 다른 서비스 빌드까지 건드리게 되므로 여기서 막는다.
COPY curriculum/__init__.py   /app/curriculum/
COPY curriculum/roadmap/      /app/curriculum/roadmap/
COPY curriculum/service/      /app/curriculum/service/
COPY curriculum/data/         /app/curriculum/data/

EXPOSE 8086

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8086/actuator/health')"

CMD ["uvicorn", "curriculum.service.app:app", "--host", "0.0.0.0", "--port", "8086"]
