FROM python:3.12-slim

WORKDIR /app

# 安装时区数据并设置上海时区
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && \
    ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo 'Asia/Shanghai' > /etc/timezone && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

EXPOSE 5000

CMD ["python", "-m", "app.main", "--port", "5000"]