# ==========================
# Build Stage
# ==========================
FROM node:22-alpine AS builder

WORKDIR /app

# Copy dependency files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build React application
RUN npm run build

# ==========================
# Production Stage
# ==========================
FROM nginx:1.28-alpine

# Remove default nginx configuration
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config
COPY nginx-spa.conf /etc/nginx/conf.d/default.conf

# Copy build artifacts
COPY --from=builder /app/build /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
