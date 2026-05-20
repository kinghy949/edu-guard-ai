FROM python:3.11-slim

WORKDIR /app

# 可选：通过 build-arg 指定 pip 镜像，国内构建建议传清华镜像加速
# 用法: docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_INDEX_URL=""
RUN if [ -n "$PIP_INDEX_URL" ]; then \
      pip config set global.index-url "$PIP_INDEX_URL"; \
    fi

COPY pyproject.toml ./
COPY . .

RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
