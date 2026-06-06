FROM python:3.11-slim

WORKDIR /app

ARG OSV_SCANNER_VERSION=2.3.8
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL "https://github.com/google/osv-scanner/releases/download/v${OSV_SCANNER_VERSION}/osv-scanner_linux_amd64" \
        -o /usr/local/bin/osv-scanner \
    && chmod +x /usr/local/bin/osv-scanner \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

ENTRYPOINT ["orchestrator"]
CMD ["--help"]
