FROM mw-base

RUN mkdir /app/cache

WORKDIR /app
ENV PORT=9123
EXPOSE 9123