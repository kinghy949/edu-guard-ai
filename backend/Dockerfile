FROM python:3.11-slim

WORKDIR /app

# 国内默认走清华镜像（覆盖最全；阿里云 mirror 部分包元数据会回链 pypi 触发超时）。
# 国外服务器：--build-arg PIP_INDEX_URL=https://pypi.org/simple --build-arg PIP_TRUSTED_HOST=
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
ENV PIP_INDEX_URL=$PIP_INDEX_URL
ENV PIP_TRUSTED_HOST=$PIP_TRUSTED_HOST
ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=10
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# 1) 预装 build 后端，避免 pip install -e . 触发 PEP 517 隔离环境
#    （原本会另起一个隔离 pip 重新装 setuptools，慢且常超时）
RUN pip install --no-cache-dir setuptools>=68 wheel

COPY pyproject.toml ./
COPY . .

# 2) --no-build-isolation 复用上面已装的 setuptools，跳过隔离构建
RUN pip install --no-cache-dir --no-build-isolation -e .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
