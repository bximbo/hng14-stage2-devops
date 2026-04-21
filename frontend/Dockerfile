FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json .

RUN npm ci --omit=dev

FROM node:20-alpine

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY package.json app.js ./
COPY views ./views

EXPOSE 3000

HEALTHCHECK --interval=5s --timeout=2s --start-period=2s --retries=3 \
    CMD wget -qO- http://127.0.0.1:3000/health || exit 1

CMD ["npm", "start"]
