# Caddy with Coraza WAF - 部署指南

## 🚀 快速启动（推荐）

```bash
# 一键启动 Caddy（自动构建镜像）
cd /path/to/your/project
./caddy/start.sh
```

---

## 📦 手动部署步骤

### 1. 准备环境

```bash
# 创建必要的目录
mkdir -p caddy/{logs,data,config,geoip,waf}
```

### 2. 下载 GeoIP 数据库（可选）

```bash
# 下载 GeoLite2-City 数据库
cd caddy/geoip
wget https://git.io/GeoLite2-City.mmdb
# 或从 MaxMind 官网下载: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
```

### 3. 构建 Caddy 镜像

```bash
# 构建包含 Coraza WAF 的 Caddy 镜像
docker-compose build caddy.service
```

这个过程会：
- 使用 `xcaddy` 构建 Caddy
- 集成 `coraza-caddy/v2` WAF 模块
- 集成 `caddy-dns/cloudflare` DNS 插件
- 构建时间约 3-5 分钟

### 4. 启动服务

```bash
# 启动 Caddy
docker-compose up -d caddy.service

# 查看日志
docker-compose logs -f caddy.service
```

### 5. 验证部署

```bash
# 检查服务状态
docker-compose ps caddy.service

# 测试健康检查
curl http://localhost/health

# 测试 WAF（应该返回 403）
curl "http://localhost/v1/besrv/api?id=1' OR '1'='1"
```

---

## 🛡️ WAF 功能验证

### SQL 注入防护测试

```bash
# 应该被阻止（403 Forbidden）
curl -v "http://localhost/v1/besrv/api?id=1' OR '1'='1"
curl -v "http://localhost/v1/besrv/api?name=admin'--"
curl -v "http://localhost/v1/besrv/api?q=SELECT * FROM users"

# 正常请求应该成功（200 OK）
curl -v "http://localhost/v1/besrv/api?id=123"
```

### XSS 防护测试

```bash
# 应该被阻止（403 Forbidden）
curl -v "http://localhost/v1/besrv/api?name=<script>alert(1)</script>"
curl -v "http://localhost/v1/besrv/api?html=<iframe src=evil.com>"
curl -v "http://localhost/v1/besrv/api?js=javascript:alert(1)"

# 正常请求应该成功
curl -v "http://localhost/v1/besrv/api?name=John"
```

### 路径遍历防护测试

```bash
# 应该被阻止（403 Forbidden）
curl -v "http://localhost/.env"
curl -v "http://localhost/.git/config"
curl -v "http://localhost/backup/database.sql"
curl -v "http://localhost/phpMyAdmin/"

# 正常请求应该成功
curl -v "http://localhost/v1/besrv/api"
```

### Content-Type 验证测试

```bash
# POST 请求没有正确的 Content-Type 会被拒绝（400 Bad Request）
curl -X POST "http://localhost/v1/besrv/api" \
  -d "data=test"

# 正确的请求（200 OK）
curl -X POST "http://localhost/v1/besrv/api" \
  -H "Content-Type: application/json" \
  -d '{"key":"value"}'
```

---

## 📊 监控和日志

### 查看 WAF 审计日志

```bash
# 实时查看 WAF 拦截记录
docker exec cancan_caddy tail -f /var/log/caddy/waf-audit.log
```

### 查看访问日志

```bash
# JSON 格式访问日志
docker exec cancan_caddy tail -f /var/log/caddy/access.json

# 人类可读的访问日志
docker exec cancan_caddy tail -f /var/log/caddy/access.log
```

### 查看 Caddy 日志

```bash
# 容器日志
docker-compose logs -f caddy.service

# 进入容器查看详细日志
docker exec -it cancan_caddy sh
ls -lh /var/log/caddy/
```

---

## ⚙️ 配置调整

### 修改 WAF 偏执级别

编辑 `caddy/waf/coraza.conf`：

```conf
# 偏执级别：1=宽松, 2=标准, 3=严格, 4=极端
setvar:tx.paranoia_level=2
```

修改后重启：
```bash
docker-compose restart caddy.service
```

### 添加 IP 白名单

编辑 `caddy/waf/coraza.conf`，添加：

```conf
# 允许特定 IP 绕过 WAF
SecRule REMOTE_ADDR "@ipMatch 192.168.1.0/24" \
  "id:900401,phase:1,pass,nolog,ctl:ruleEngine=Off"
```

### 禁用特定 WAF 规则

如果遇到误报，可以禁用特定规则：

```conf
# 禁用规则 ID 900510（SQL 注入检测）
SecRuleRemoveById 900510
```

---

## 🔧 故障排查

### Caddy 无法启动

```bash
# 查看详细错误
docker-compose logs caddy.service

# 常见问题：
# 1. 端口 80/443 被占用
# 2. Caddyfile 语法错误
# 3. WAF 配置文件路径不正确
```

### WAF 误报（阻止正常请求）

1. **查看审计日志**找到触发的规则 ID：
   ```bash
   docker exec cancan_caddy tail -100 /var/log/caddy/waf-audit.log
   ```

2. **临时禁用规则**（在 `coraza.conf` 中）：
   ```conf
   SecRuleRemoveById <规则ID>
   ```

3. **降低偏执级别**（改为 1）

### 验证 Coraza 模块是否加载

```bash
# 进入容器
docker exec -it cancan_caddy sh

# 列出所有模块
/usr/bin/caddy list-modules | grep coraza

# 应该看到：
# http.handlers.coraza_waf
```

---

## 📈 性能建议

### 生产环境优化

1. **关闭调试日志**：
   ```conf
   SecDebugLogLevel 3  # 改为 3（仅警告）
   ```

2. **限制审计日志**：
   ```conf
   SecAuditEngine RelevantOnly
   SecAuditLogRelevantStatus "^(?:5|4(?!04))"
   ```

3. **关闭响应体检查**（已默认关闭）：
   ```conf
   SecResponseBodyAccess Off
   ```

---

## 🌐 完整 OWASP CRS（可选）

如果需要使用完整的 OWASP Core Rule Set：

```bash
# 下载 OWASP CRS
cd caddy/waf
wget https://github.com/coreruleset/coreruleset/archive/v4.0.0.tar.gz
tar -xzf v4.0.0.tar.gz
mv coreruleset-4.0.0 owasp-crs

# 复制配置文件
cp owasp-crs/crs-setup.conf.example owasp-crs/crs-setup.conf

# 更新 coraza.conf，添加：
# Include /etc/caddy/waf/owasp-crs/crs-setup.conf
# Include /etc/caddy/waf/owasp-crs/rules/*.conf

# 重新构建和启动
docker-compose build caddy.service
docker-compose up -d caddy.service
```

---

## 📚 相关文档

- [Caddy 完整配置说明](./README.md)
- [API 文档 v3.0](../OPSBFFSRV_API_DOCUMENTATION_V3.md)
- [Coraza WAF 官方文档](https://coraza.io/docs/)
- [OWASP CRS 文档](https://coreruleset.org/docs/)

---

## ⚠️ 安全提醒

1. ✅ **定期更新** WAF 规则和 Caddy 版本
2. ✅ **监控日志** 每日检查 WAF 审计日志
3. ✅ **测试先行** 在测试环境验证配置后再应用到生产
4. ✅ **备份配置** 修改前先备份配置文件
5. ✅ **调整规则** 根据业务需求调整 WAF 规则，避免误报

---

**部署完成！**

现在您的 API 网关已经启用了企业级的 WAF 防护 🛡️
