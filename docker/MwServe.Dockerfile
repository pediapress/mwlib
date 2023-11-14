FROM mw-base

WORKDIR /app

EXPOSE 8080
CMD ["mw-serve-ctl", "serve_ctl"]
