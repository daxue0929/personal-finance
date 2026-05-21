FROM python:3.12-slim

WORKDIR /app

# 设置上海时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["python", "-m", "app.main", "--port", "5000"]
