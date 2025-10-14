FROM python:3.10

RUN pip install flask waitress fpdf werkzeug pillow pyyaml

WORKDIR /proxyserver
COPY . .
ENTRYPOINT ["waitress-serve", "flask_app:app"]
