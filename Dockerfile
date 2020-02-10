FROM python:3.7-slim

COPY ./app /app

RUN apt-get clean \
    && apt-get -y update

RUN apt-get -y install nginx \
    && apt-get -y install python3-dev \
    && apt-get -y install libpcre3 libpcre3-dev \
    && apt-get -y install build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -r app/requirements.txt

COPY ./tests /tests
RUN pytest /tests && rm -rf /tests

COPY nginx.conf /etc/nginx

WORKDIR /app

CMD ["./start.sh"]
