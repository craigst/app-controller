FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install adb (and optionally fastboot) 
RUN apt-get update && apt-get install -y --no-install-recommends \
    android-tools-adb \
    android-tools-fastboot \
    #add wget for getting new apk
    wget

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app/

EXPOSE 5000

CMD ["python", "app.py"]
# need to add wget