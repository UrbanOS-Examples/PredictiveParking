FROM python:3

COPY ./requirements.txt /app/requirements.txt


WORKDIR /app

RUN apt-get update -y
RUN apt-get install -y python3-dev
RUN pip install -r requirements.txt

COPY ./models/* /app/models/
COPY ./test.py /app/test.py
COPY ./meter_config/* /app/meter_config/
COPY app.py /app/app.py


ENTRYPOINT [ "python" ]

CMD [ "app.py" ]