FROM python:3.11-slim

WORKDIR /app

# 国内默认走阿里云镜像。国外: --build-arg PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ARG PIP_TRUSTED_HOST=mirrors.aliyun.com
ENV PIP_INDEX_URL=$PIP_INDEX_URL
ENV PIP_TRUSTED_HOST=$PIP_TRUSTED_HOST
ENV PIP_DEFAULT_TIMEOUT=180
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装 uv（Rust 实现的包管理器，HTTP/2 并发 + 强重试，对国内烂网络容忍度远高于 pip）
RUN pip install --no-cache-dir uv

# uv 也读 PIP_INDEX_URL，无需额外配置
ENV UV_HTTP_TIMEOUT=180
ENV UV_CONCURRENT_DOWNLOADS=4

COPY pyproject.toml ./
COPY . .

# uv pip install: 安装到系统 Python，速度比 pip 快很多
RUN uv pip install --system --no-cache -e .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
