FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Add apt-cacher-ng proxy config:
RUN echo 'Acquire::HTTP::Proxy "http://192.168.1.96:3142";' \
    > /etc/apt/apt.conf.d/01proxy

WORKDIR /app

# Install packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    android-tools-adb \
    android-tools-fastboot \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --upgrade pip --default-timeout=500 \
    && pip install --default-timeout=500 -r requirements.txt


COPY . /app/

EXPOSE 5000
CMD ["python", "app.py"]
