# CorrerIA: imagem do app do Home Assistant.
# Só Python e a biblioteca padrão; nenhum pacote extra. As fontes vêm junto, em app/www/fonts.
FROM python:3.12-alpine

RUN apk add --no-cache tzdata

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY app/ /app/

CMD ["python3", "/app/server.py"]
