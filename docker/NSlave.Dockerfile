FROM mw-base

RUN mkdir /app/cache

WORKDIR /app
ENV PORT=9123
EXPOSE 9123
CMD ["nslave", "--cachedir", "cache", "--host", "q_serve", "--port", "8090", "--numprocs", "2", "-s", "makezip"]
