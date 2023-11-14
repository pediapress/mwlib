FROM mw-base

RUN mkdir /cache-dir

WORKDIR /app
EXPOSE 8080
CMD ["nslave", "--cachedir", "/cache-dir"]
