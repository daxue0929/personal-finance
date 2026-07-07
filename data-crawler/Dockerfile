FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 备份一个镜像加速的源
# https://pypi.tuna.tsinghua.edu.cn/simple/
# https://mirrors.aliyun.com/pypi/simple/

COPY . .

# web 进程暴露 5000，scheduler 进程暴露 5001（由 docker-compose 指定 CMD）
EXPOSE 5000 5001

# 默认入口由 docker-compose 通过 command 指定：
#   web:        python -m app.web --port 5000
#   scheduler:  python -m app.scheduler --port 5001