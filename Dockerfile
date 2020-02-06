FROM python:3.7-slim

COPY ./requirements.txt /app/requirements.txt

WORKDIR /app

RUN apt-get clean \
    && apt-get -y update

RUN apt-get -y install nginx \
    && apt-get -y install python3-dev \
    && apt-get -y install libpcre3 libpcre3-dev \
    && apt-get -y install build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt

COPY ./models/* /app/models/
COPY ./predictor.py /app/predictor.py
COPY ./meter_config/* /app/meter_config/
COPY cli.py /app/cli.py
COPY app.py /app/app.py
COPY uwsgi.ini /app/uwsgi.ini
COPY nginx.conf /etc/nginx
COPY start.sh /app/start.sh

RUN chmod +x /app/start.sh

CMD ["./start.sh"]
