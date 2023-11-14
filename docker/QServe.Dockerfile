FROM mw-base

RUN apt-get update && apt-get install -y git

RUN mkdir /qserve

RUN git clone https://github.com/pediapress/qserve.git /qserve

RUN echo "-e /qserve" >> /app/requirements/base.in

WORKDIR /app

RUN make install

RUN python3 setup.py build
RUN python3 setup.py install

EXPOSE 8080

WORKDIR /app

CMD ["mw-qserve", "-p", "8080", "-i", "0.0.0.0"]
