FROM crpi-uuz3ex5s26cqqb5m.cn-shanghai.personal.cr.aliyuncs.com/hetu_xinhong/python:3.11.4-slim-bullseye as base

# 替换为阿里云镜像源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list \
    && sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

RUN apt-get update && apt-get install -y \
  gcc \
  && rm -rf /var/lib/apt/lists/*

# 将 pip 镜像源设置为阿里云
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple

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