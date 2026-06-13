# Caddy with Coraza WAF - 使用指南

本项目使用**自定义构建的 Caddy**，集成了 **Coraza WAF（Web Application Firewall）** 模块，提供企业级的安全防护。

---

## 🛡️ 安全特性

### 已启用的防护功能

1. **SQL 注入防护** - 检测和阻止 SQL 注入攻击
2. **XSS 防护** - 阻止跨站脚本攻击
3. **路径遍历防护** - 防止访问敏感文件（.env, .git, backup 等）
4. **协议违规检测** - 验证 HTTP 协议合规性
5. **文件扩展名过滤** - 阻止访问危险文件类型
6. **请求大小限制** - 防止 DoS 攻击（最大 10MB）
7. **Content-Type 验证** - API 请求必须使用 `application/json`

### WAF 配置

- **偏执级别**: 2（增强保护）
- **入站异常阈值**: 5
- **出站异常阈值**: 4
- **审计日志**: 仅记录相关事件（4xx/5xx 错误）

---

## 📁 目录结构

```
caddy/
├── Dockerfile              # 自定义 Caddy 构建文件（包含 Coraza）
├── Caddyfile              # Caddy 主配置文件
├── waf/
│   └── coraza.conf        # Coraza WAF 配置
├── logs/
│   ├── access.log         # 访问日志
│   ├── access.json        # JSON 格式访问日志
│   ├── waf-audit.log      # WAF 审计日志
│   └── waf-debug.log      # WAF 调试日志
├── data/                  # Caddy 数据目录（证书等）
├── config/                # Caddy 配置目录
└── geoip/                 # GeoIP 数据库目录
    └── GeoLite2-City.mmdb
```

---

## 🚀 构建和启动

### 1. 构建 Caddy 镜像

Docker Compose 会自动构建包含 Coraza WAF 的 Caddy 镜像：

```bash
# 构建镜像
docker-compose build caddy.service

# 或直接启动（会自动构建）
docker-compose up -d caddy.service
```

### 2. 验证 WAF 是否启用

```bash
# 查看 Caddy 日志
docker-compose logs caddy.service

# 应该看到类似的输出：
# {"level":"info","ts":...,"msg":"using provided configuration","adapter":"caddyfile"}
```

### 3. 测试 WAF 防护

#### 测试 SQL 注入防护

```bash
# 应该被阻止（返回 403）
curl "http://localhost/v1/besrv/api?id=1' OR '1'='1"

# 正常请求应该成功
curl "http://localhost/v1/besrv/api?id=123"
```

#### 测试 XSS 防护

```bash
# 应该被阻止（返回 403）
curl "http://localhost/v1/besrv/api?name=<script>alert(1)</script>"

# 正常请求应该成功
curl "http://localhost/v1/besrv/api?name=John"
```

#### 测试路径遍历防护

```bash
# 应该被阻止（返回 403）
curl "http://localhost/.env"
curl "http://localhost/.git/config"
curl "http://localhost/backup/database.sql"

# 正常请求应该成功
curl "http://localhost/health"
```

#### 测试 API Content-Type 验证

```bash
# POST 请求没有 Content-Type: application/json 会被拒绝
curl -X POST "http://localhost/v1/besrv/api" \
  -d "data=test"  # 应该返回 400

# 正确的请求
curl -X POST "http://localhost/v1/besrv/api" \
  -H "Content-Type: application/json" \
  -d '{"key":"value"}'  # 应该成功
```

---

## 📊 WAF 日志

### 审计日志

WAF 会记录所有被阻止的请求到审计日志：

```bash
# 查看 WAF 审计日志
docker exec cancan_caddy tail -f /var/log/caddy/waf-audit.log
```

日志格式示例：
```
[2025-01-01T10:30:00Z] [client 1.2.3.4] [id "900510"] [msg "SQL Injection Attempt Detected"] [uri "/v1/besrv/api?id=1' OR '1'='1"]
```

### 调试日志

开发环境可以查看详细的 WAF 调试日志：

```bash
# 查看 WAF 调试日志
docker exec cancan_caddy tail -f /var/log/caddy/waf-debug.log
```

---

## ⚙️ WAF 配置调整

### 修改偏执级别

编辑 `caddy/waf/coraza.conf`：

```conf
# 调整偏执级别（1-4）
SecAction \
  "id:900000,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.paranoia_level=3"  # 改为 1（宽松）或 4（严格）
```

### 添加 IP 白名单

在 `caddy/waf/coraza.conf` 中添加：

```conf
# 允许特定 IP 绕过 WAF
SecRule REMOTE_ADDR "@ipMatch 192.168.1.0/24" \
  "id:900401,\
  phase:1,\
  pass,\
  nolog,\
  ctl:ruleEngine=Off"
```

### 添加 IP 黑名单

```conf
# 阻断特定 IP
SecRule REMOTE_ADDR "@ipMatch 1.2.3.4" \
  "id:900402,\
  phase:1,\
  deny,\
  status:403,\
  log,\
  msg:'Blocked IP address'"
```

### 添加自定义规则

```conf
# 阻止特定 User-Agent
SecRule REQUEST_HEADERS:User-Agent "@contains BadBot" \
  "id:900700,\
  phase:1,\
  deny,\
  status:403,\
  log,\
  msg:'Blocked bot user-agent'"
```

### 修改后重启 Caddy

```bash
docker-compose restart caddy.service
```

---

## 🔧 故障排查

### WAF 误报（False Positive）

如果正常请求被 WAF 阻止：

1. **查看审计日志**，找到触发的规则 ID
   ```bash
   docker exec cancan_caddy tail -100 /var/log/caddy/waf-audit.log
   ```

2. **禁用特定规则**（在 `coraza.conf` 中添加）
   ```conf
   # 禁用规则 ID 900510
   SecRuleRemoveById 900510
   ```

3. **调整偏执级别**（降低到 1）

### Caddy 启动失败

```bash
# 查看详细错误
docker-compose logs caddy.service

# 常见问题：
# 1. Caddyfile 语法错误
# 2. WAF 配置文件路径不正确
# 3. 端口被占用
```

### 验证 Coraza 模块是否加载

```bash
# 进入容器
docker exec -it cancan_caddy sh

# 检查 Caddy 版本和模块
/usr/bin/caddy version
/usr/bin/caddy list-modules | grep coraza
```

---

## 📈 性能优化

### 1. 关闭响应体检查

响应体检查会影响性能，生产环境建议关闭：

```conf
# 在 coraza.conf 中已默认关闭
SecResponseBodyAccess Off
```

### 2. 调整日志级别

生产环境降低调试日志级别：

```conf
SecDebugLogLevel 3  # 3=警告, 5=详细（开发环境）
```

### 3. 限制审计日志

只记录阻断事件：

```conf
SecAuditEngine RelevantOnly
SecAuditLogRelevantStatus "^(?:5|4(?!04))"
```

---

## 🌐 OWASP CRS（可选）

如果需要使用完整的 **OWASP Core Rule Set**：

### 1. 下载 CRS

```bash
cd caddy/waf
wget https://github.com/coreruleset/coreruleset/archive/v4.0.0.tar.gz
tar -xzf v4.0.0.tar.gz
mv coreruleset-4.0.0 owasp-crs
```

### 2. 更新 coraza.conf

```conf
# 包含 OWASP CRS
Include /etc/caddy/waf/owasp-crs/crs-setup.conf.example
Include /etc/caddy/waf/owasp-crs/rules/*.conf
```

### 3. 重新构建镜像

```bash
docker-compose build caddy.service
docker-compose up -d caddy.service
```

---

## 📚 参考资料

- [Caddy 官方文档](https://caddyserver.com/docs/)
- [Coraza WAF 文档](https://coraza.io/docs/)
- [OWASP Core Rule Set](https://owasp.org/www-project-modsecurity-core-rule-set/)
- [Caddy Coraza 模块](https://github.com/corazawaf/coraza-caddy)

---

## ⚠️ 安全建议

1. **定期更新** Caddy 和 Coraza 模块
2. **定期审查** WAF 审计日志
3. **调整规则** 根据实际业务需求调整 WAF 规则
4. **监控误报** 及时处理误报，避免影响正常业务
5. **备份配置** 修改配置前先备份
6. **测试环境** 在测试环境验证配置后再应用到生产环境

---

## 📞 支持

如有问题，请查看：
- WAF 审计日志: `/var/log/caddy/waf-audit.log`
- WAF 调试日志: `/var/log/caddy/waf-debug.log`
- Caddy 日志: `docker-compose logs caddy.service`
