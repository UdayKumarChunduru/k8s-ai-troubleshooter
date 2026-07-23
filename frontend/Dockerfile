FROM nginxinc/nginx-unprivileged:1.27-alpine

ENV BACKEND_HOST=backend:8000

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY index.html app.js style.css /usr/share/nginx/html/

EXPOSE 8080
