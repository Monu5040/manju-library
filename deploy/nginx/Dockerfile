# syntax=docker/dockerfile:1
# Built from the repository root: docker build -f deploy/nginx/Dockerfile .

FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:stable-alpine
# The image's entrypoint renders *.template into conf.d, filling in ${SERVER_NAME}.
COPY deploy/nginx/templates/ /etc/nginx/templates/
COPY deploy/nginx/snippets/ /etc/nginx/snippets/
COPY --chmod=755 deploy/nginx/docker-entrypoint.d/ /docker-entrypoint.d/
COPY --from=build /app/dist /usr/share/nginx/html
