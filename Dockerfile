FROM python:3.7-slim

COPY ./app /app

WORKDIR /app

RUN apt-get clean \
    && apt-get -y update

RUN apt-get -y install nginx \
    && apt-get -y install python3-dev \
    && apt-get -y install libpcre3 libpcre3-dev \
    && apt-get -y install build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY nginx.conf /etc/nginx

RUN pip install -r requirements.txt

CMD ["./start.sh"]
