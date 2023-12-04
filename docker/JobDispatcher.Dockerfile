FROM mw-base

WORKDIR /app
ENV PORT=8899
EXPOSE 8899
CMD ["nserve", "q_serve:8090"]
