# syntax=docker/dockerfile:1.7-labs
# Shared Python runtime image for infrasrv / opsbffsrv / controllersrv.
#
# The image installs the published `cancan-microstack` package (and its bundled
# service dependencies) from PyPI — it does NOT copy any source from the build
# context. A clean `pip install cancan-microstack` workspace can therefore build
# and run the stack without an `src/` tree.
#
# Build args (injected automatically by the `cancan` CLI):
#   CANCAN_VERSION   exact released version to install (keeps container == host CLI)
#   CANCAN_PIP_SPEC  override the whole pip spec (e.g. a local wheel / VCS url) for dev
#   PIP_INDEX_URL    custom index (mirrors / private index)

ARG PYTHON_VERSION=3.13-slim

FROM python:${PYTHON_VERSION} AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && ln -fs /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

ARG CANCAN_VERSION
ARG CANCAN_PIP_SPEC=
ARG PIP_INDEX_URL=

# Install cancan-microstack from PyPI (or the override spec). Its dependencies
# (linglong-web[all], dragonfly-container[all], jinja2, ...) come transitively.
RUN --mount=type=cache,target=/root/.cache/pip \
    set -eu; \
    PIP_SPEC="${CANCAN_PIP_SPEC:-cancan-microstack==${CANCAN_VERSION}}"; \
    if [ "${PIP_SPEC}" = "cancan-microstack==" ]; then \
        echo "ERROR: set CANCAN_VERSION or CANCAN_PIP_SPEC (the 'cancan' CLI sets this automatically)" >&2; \
        exit 1; \
    fi; \
    pip install --upgrade pip; \
    pip install --no-warn-script-location ${PIP_INDEX_URL:+--index-url "${PIP_INDEX_URL}"} "${PIP_SPEC}"

RUN mkdir -p /app/server_log_data /app/ddl

EXPOSE 8080

# The concrete service is selected by compose, e.g.:
#   python -m cancan_microstack.cmd.infrasrv.run
CMD ["python", "-c", "import sys; sys.stderr.write('Specify a service module via compose, e.g. python -m cancan_microstack.cmd.infrasrv.run\\n'); sys.exit(1)"]
