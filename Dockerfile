FROM python:3.12-slim AS builder
WORKDIR /build
COPY setup.py pyproject.toml .
COPY lib ./lib
COPY bin ./bin
COPY externum ./externum
RUN pip install --prefix=/install .
FROM python:3.12-slim
COPY --from=builder /install /usr/local
ENTRYPOINT ["externum"]
