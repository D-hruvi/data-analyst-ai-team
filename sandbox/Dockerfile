FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/mpl \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sandbox

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

WORKDIR /app
COPY runner.py /app/runner.py

USER sandbox
ENTRYPOINT ["python", "/app/runner.py"]
