FROM python:3.14-slim

ARG PROOFCODE_USER_ID=10001
ARG PROOFCODE_GROUP_ID=10001

RUN groupadd --gid "${PROOFCODE_GROUP_ID}" proofcode \
    && useradd \
        --uid "${PROOFCODE_USER_ID}" \
        --gid "${PROOFCODE_GROUP_ID}" \
        --create-home \
        --shell /usr/sbin/nologin \
        proofcode \
    && python -m pip install --no-cache-dir "pytest==8.4.2"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
USER 10001:10001
