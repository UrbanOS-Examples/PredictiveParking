FROM python:3.8

RUN apt-get clean \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get -y update

RUN apt-get -y install nginx \
    && apt-get -y install python3-dev \
    && apt-get -y install libpcre3 libpcre3-dev \
    && apt-get -y install build-essential \
    && apt-get -y install unixodbc-dev \
    && apt-get -y install locales \
    && ACCEPT_EULA=Y apt-get -y install msodbcsql17 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install 'pipenv==2018.11.26'

ADD Pipfile* /

RUN pipenv lock --requirements > requirements.txt \
    && pip3 install --requirement requirements.txt \
    && pipenv install --dev

COPY app /app
RUN chmod +x app/start.sh
RUN chmod +x app/train.sh

COPY ./tests /tests
RUN pipenv run pytest /tests \
    && rm -rf /tests \
    && pipenv --rm

COPY train.py /

COPY report.py /

COPY nginx.conf /etc/nginx

WORKDIR /app