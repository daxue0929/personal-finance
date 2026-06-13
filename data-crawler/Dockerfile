FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 备份一个镜像加速的源
# https://pypi.tuna.tsinghua.edu.cn/simple/
# https://mirrors.aliyun.com/pypi/simple/

COPY . .

EXPOSE 5000

CMD ["python", "-m", "app.main", "--port", "5000"]