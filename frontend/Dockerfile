# --- Build stage -------------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app

# Next.js bakes rewrite destinations at build time, so the backend URL the
# browser-facing /api/v1 proxy points at must be known here. Defaults to the
# compose service name; override via build args for other topologies.
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=$BACKEND_URL
ENV NEXT_TELEMETRY_DISABLED=1

COPY package*.json .
RUN npm ci

COPY . .
RUN npm run build

# --- Runtime stage -----------------------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# The standalone server reads these at runtime; bind to all interfaces so the
# mapped port is reachable, and keep the backend URL for the SSE/health routes.
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
ENV BACKEND_URL=http://backend:8000

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
