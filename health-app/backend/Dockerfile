FROM node:20-slim
WORKDIR /app

RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm ci

COPY prisma ./prisma
RUN npx prisma generate

COPY dist ./dist

EXPOSE 8080
CMD ["sh", "-c", "npx prisma db push --accept-data-loss && node dist/server.js"]