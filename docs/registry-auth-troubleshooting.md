# 阿里云容器镜像服务认证问题排查

## 错误信息

```
Error: Error response from daemon: Get "https://crpi-uuz3ex5s26cqqb5m.cn-shanghai.personal.cr.aliyuncs.com/v2/": unauthorized: authentication required
```

## 问题原因

GitHub Secrets 中的 `REGISTRY_USERNAME` 或 `REGISTRY_PASSWORD` 未设置或设置错误。

## 解决方案

### 1. 检查 GitHub Secrets 是否已设置

```bash
# 使用 GitHub CLI 查看已设置的 secrets
gh secret list

# 检查特定的 secret（只显示名称，不显示值）
gh secret list | grep REGISTRY
```

### 2. 设置镜像仓库凭证

#### 方式1：使用脚本设置（推荐）

```bash
# 生成配置文件模板
./scripts/setup-github-secrets.sh --create-config

# 编辑配置文件，填写 REGISTRY_USERNAME 和 REGISTRY_PASSWORD
vim github-secrets.conf

# 从配置文件设置
./scripts/setup-github-secrets.sh --config github-secrets.conf
```

#### 方式2：手动设置

```bash
# 设置用户名
echo "your-registry-username" | gh secret set REGISTRY_USERNAME

# 设置密码
echo "your-registry-password" | gh secret set REGISTRY_PASSWORD
```

#### 方式3：交互式设置

```bash
./scripts/setup-github-secrets.sh --interactive
```

### 3. 阿里云容器镜像服务凭证说明

#### 个人版镜像仓库

- **用户名**: 阿里云账号用户名（通常是邮箱或手机号）
- **密码**: 阿里云账号密码，或设置的镜像仓库独立密码

#### 企业版镜像仓库

- **用户名**: 阿里云账号用户名或 RAM 子账号用户名
- **密码**: 阿里云账号密码，或 RAM 子账号密码

#### 使用访问凭证（推荐）

如果使用访问凭证（AccessKey），需要：
1. 登录阿里云控制台
2. 进入容器镜像服务
3. 设置访问凭证
4. 使用凭证的用户名和密码

### 4. 验证设置

```bash
# 查看已设置的 secrets（只显示名称）
gh secret list

# 应该能看到：
# REGISTRY_USERNAME
# REGISTRY_PASSWORD
```

### 5. 重新触发部署

设置完成后，重新推送 tag 触发部署：

```bash
# 删除旧的 tag（如果需要）
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0

# 重新创建并推送 tag
git tag v1.0.0
git push origin v1.0.0
```

## 常见问题

### Q: 用户名和密码是什么格式？

A: 
- 用户名：通常是邮箱地址或手机号（如：`user@example.com` 或 `13800138000`）
- 密码：阿里云账号密码，或镜像仓库独立密码

### Q: 可以使用 AccessKey 吗？

A: 可以，但需要先在容器镜像服务中设置访问凭证，然后使用凭证的用户名和密码。

### Q: 如何测试凭证是否正确？

A: 可以在本地测试：

```bash
docker login crpi-uuz3ex5s26cqqb5m.cn-shanghai.personal.cr.aliyuncs.com
# 输入用户名和密码
# 如果登录成功，说明凭证正确
```

### Q: 密码包含特殊字符怎么办？

A: 如果密码包含特殊字符，建议：
1. 使用配置文件方式设置（避免命令行转义问题）
2. 或使用 GitHub Web 界面手动设置

## 参考文档

- [阿里云容器镜像服务文档](https://help.aliyun.com/product/60716.html)
- [GitHub Secrets 管理文档](./github-secrets-management.md)

