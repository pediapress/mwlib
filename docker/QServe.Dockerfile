FROM mw-base

EXPOSE 8080

WORKDIR /app

CMD ["mw-qserve", "-p", "8090"]
