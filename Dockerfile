# ── Stage 1: Build ──
FROM python:3.12-slim AS builder
WORKDIR /build
COPY setup.py README.md ./
COPY externum/ externum/
COPY lib/ lib/
COPY bin/ bin/
RUN pip install --no-cache-dir --prefix=/install .

# ── Stage 2: Runtime ──
FROM python:3.12-slim
COPY --from=builder /install /usr/local
RUN useradd -m externum
USER externum
WORKDIR /home/externum
ENTRYPOINT ["externum"]
