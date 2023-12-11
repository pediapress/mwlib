FROM mw-base

EXPOSE 8090

WORKDIR /app

CMD ["mw-qserve", "-p", "8090"]
