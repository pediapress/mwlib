FROM mw-base

WORKDIR /app
ENV PORT=8899
EXPOSE 8899
CMD ["postman", "--port", "8090", "--host", "q_serve"]
