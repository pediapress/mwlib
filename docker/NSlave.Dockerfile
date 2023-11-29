FROM mw-base

RUN mkdir /app/cache

WORKDIR /app
ENV PORT=8898
EXPOSE 8898
CMD ["nslave", "--cachedir", "cache", "--host", "q_serve", "--port", "8090", "--url", "http://localhost:9123/cache", "--numprocs", "2", "-s", "makezip", "--serve-files-port", "9123"]
