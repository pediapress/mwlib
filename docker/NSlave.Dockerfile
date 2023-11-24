FROM mw-base

RUN mkdir /cache-dir

WORKDIR /app
ENV PORT=8898
EXPOSE 8898
CMD ["nslave", "--cachedir", "/cache-dir", "--host", "q_serve", "--port", "8090", "--url", "https://newtools.pediapress.com/cache", "--numprocs", "2", "-s", "makezip"]
