# ---- Frontend image (static Stitch designs served by nginx) ----
FROM nginx:1.27-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/assets /usr/share/nginx/html/assets
COPY frontend/*.html /usr/share/nginx/html/

EXPOSE 8501

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=5 \
    CMD wget -qO- http://localhost:8501/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
