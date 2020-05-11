FROM python:3.7-slim

RUN apt-get clean \
    && apt-get -y update

RUN apt-get -y install nginx \
    && apt-get -y install python3-dev \
    && apt-get -y install libpcre3 libpcre3-dev \
    && apt-get -y install build-essential \
    && apt-get -y install unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY ./app /app

RUN pip install -r app/requirements.txt

RUN chmod +x app/start.sh

COPY ./tests /tests
RUN pytest /tests && rm -rf /tests

COPY train* /
RUN chmod +x /train.sh

COPY nginx.conf /etc/nginx

WORKDIR /app