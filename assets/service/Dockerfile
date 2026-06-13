# syntax=docker/dockerfile:1.7-labs

# 通用 Python 服务基础镜像
ARG PYTHON_VERSION=3.13-slim

FROM python:${PYTHON_VERSION} AS base

# 1：设置时区环境变量 ---
ENV TZ=Asia/Shanghai \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 2：安装 tzdata 并应用时区配置 ---
# 在安装 curl 的同时安装 tzdata，减少镜像层数
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && ln -fs /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone \

# =============================
# 依赖安装阶段（带缓存）
# =============================
FROM base AS deps

ARG REQUIREMENTS_FILE=requirements.txt
COPY ${REQUIREMENTS_FILE} /tmp/requirements.txt

RUN python -m venv /opt/venv

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install --no-warn-script-location -r /tmp/requirements.txt

# =============================
# 运行时镜像
# =============================
FROM base AS runtime

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY --from=deps ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# 复制代码（所有服务共享）
COPY src /app/src
COPY cmd /app/cmd
COPY tools /app/tools

# 预创建运行时需要挂载的目录
RUN mkdir -p /app/ddl /app/server_log_data

# 设置 Python 路径
ENV PYTHONPATH=/app/src:/app/src/libs:/app/cmd

EXPOSE 8080

# 启动命令由 docker-compose 的 command 字段覆盖
CMD ["python", "-c", "print('Specify command via docker-compose')"]
