# Stage 1: Build
FROM node:24-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
COPY packages/core/package.json ./packages/core/
COPY shared/package.json ./shared/
RUN npm ci
COPY tsconfig.json ./
COPY packages/ ./packages/
COPY shared/ ./shared/
RUN npm run build

# Stage 2: Production
FROM node:24-alpine AS production
RUN addgroup -g 1001 coldquery && \
    adduser -u 1001 -G coldquery -s /bin/sh -D coldquery
WORKDIR /app
COPY package.json package-lock.json ./
COPY packages/core/package.json ./packages/core/
COPY shared/ ./shared/
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=builder /app/dist ./dist
# Copy compiled shared module to node_modules (workspace symlink points to source, not compiled)
COPY --from=builder /app/dist/shared ./node_modules/@pg-mcp/shared
RUN chown -R coldquery:coldquery /app
USER coldquery
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:${PORT:-3000}/health || exit 1
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
EXPOSE 3000
CMD ["node", "dist/packages/core/src/server.js", "--transport", "http"]
