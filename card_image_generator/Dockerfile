FROM python:3.10

WORKDIR /cardgenerator
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENTRYPOINT ["waitress-serve", "proxygenserver:app"]
