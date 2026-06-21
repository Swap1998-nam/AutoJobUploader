# ─── Stage 1: Build React app ────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --legacy-peer-deps

COPY . .

# REACT_APP_API_URL is injected at build time via Jenkins
ARG REACT_APP_API_URL=/api
ENV REACT_APP_API_URL=$REACT_APP_API_URL

RUN npm run build

# ─── Stage 2: Serve via Nginx ─────────────────────────────────────────────────
FROM nginx:1.25-alpine AS runtime

# Remove default nginx page
RUN rm -rf /usr/share/nginx/html/*

# Copy built React output
COPY --from=builder /app/build /usr/share/nginx/html

# Nginx config for SPA (client-side routing)
COPY nginx-spa.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]