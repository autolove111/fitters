FROM node:20-alpine

WORKDIR /app

# 安装依赖
COPY package*.json ./
RUN npm ci --silent

# 复制源代码
COPY . .

# 开发时使用 vite/uni 的 dev:h5（绑定到 0.0.0.0:5173）
EXPOSE 5174
ENV PORT=5174

CMD ["sh", "-c", "npm run dev:h5 -- --host 0.0.0.0 --port 5174"]
