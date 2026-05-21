FROM python:3.11-slim

WORKDIR /app

# 默认走清华 pip 镜像（覆盖国内 90% 的部署场景）。
# 国外服务器或想用官方源：--build-arg PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip config set global.index-url "$PIP_INDEX_URL" \
    && pip config set global.trusted-host "$(echo $PIP_INDEX_URL | awk -F/ '{print $3}')"

COPY pyproject.toml ./
COPY . .

RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
