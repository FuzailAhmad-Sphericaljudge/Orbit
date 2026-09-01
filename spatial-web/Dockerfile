FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_DEV_USER_ID=
ARG VITE_DEV_USER_ROLE=observer
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_DEV_USER_ID=$VITE_DEV_USER_ID
ENV VITE_DEV_USER_ROLE=$VITE_DEV_USER_ROLE
RUN npm run build

FROM nginx:1.29.7-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=20s --timeout=5s --retries=5 CMD wget -q -O - http://127.0.0.1:8080/ >/dev/null || exit 1
