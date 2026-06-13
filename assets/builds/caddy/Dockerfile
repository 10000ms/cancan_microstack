# Caddy with Coraza WAF
# 使用 xcaddy 构建包含 Coraza WAF 模块的 Caddy

FROM caddy:2-builder-alpine AS builder

# Go module download mirrors for restricted networks (override via build args).
# 受限网络下的 Go 模块代理（可通过 build args 覆盖）。
ARG GOPROXY=https://goproxy.cn,https://proxy.golang.org,direct
ARG GOSUMDB=sum.golang.google.cn
ENV GOPROXY=${GOPROXY}
ENV GOSUMDB=${GOSUMDB}

# 使用 xcaddy 构建带有 Coraza WAF 的 Caddy
RUN xcaddy build \
    --with github.com/corazawaf/coraza-caddy/v2 \
    --with github.com/mholt/caddy-ratelimit \
    --with github.com/caddy-dns/cloudflare

# 最终镜像
FROM alpine:latest

# 安装运行时依赖
RUN apk add --no-cache \
    ca-certificates \
    mailcap \
    curl \
    wget

# 从 builder 阶段复制编译好的 Caddy
COPY --from=builder /usr/bin/caddy /usr/bin/caddy

# 创建必要的目录
RUN mkdir -p /etc/caddy /data /config /var/log/caddy /usr/share/GeoIP /srv/www

# 设置工作目录
WORKDIR /srv

# 暴露端口
EXPOSE 80 443 2019

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:2019/config/ || exit 1

# 启动 Caddy
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
