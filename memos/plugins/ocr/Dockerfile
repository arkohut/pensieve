FROM python:3.12

RUN apt-get update && apt-get install -y \
    # build-essential \
    libssl-dev \
    libffi-dev \
    libbz2-dev \
    liblzma-dev \
    libz-dev \
    libgl1-mesa-glx \
    libpng-dev \ 
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
