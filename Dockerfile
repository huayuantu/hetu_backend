FROM python:3.12-slim-bookworm AS base


RUN apt-get update && apt-get install -y \
  gcc \
  && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install uv

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc

# Copying requirements of a project
COPY pyproject.toml uv.lock /app/src/
WORKDIR /app/src

# 安装依赖
RUN uv sync --frozen

# Removing gcc
RUN apt-get purge -y \
  gcc \
  && rm -rf /var/lib/apt/lists/*

# 拷贝项目代码设置工作目录
COPY . /app/src/

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS collector

# 安装守护进程工具
RUN uv pip install supervisor