# 环境变量文件说明

项目中有两个环境变量相关的文件，用途不同：

## 文件对比

### `env.template`
- **用途**: CI/CD 自动生成 `.env` 文件
- **格式**: 包含 `${VAR}` 占位符
- **使用场景**: GitHub Actions 部署时自动生成 `.env` 文件
- **示例**:
  ```bash
  SECRET_KEY=${SECRET_KEY}
  DATABASE_URL=${DATABASE_URL}
  ```

### `env.example`
- **用途**: 文档参考和本地开发
- **格式**: 包含示例值
- **使用场景**: 
  - 开发者参考需要配置哪些环境变量
  - 本地开发时复制为 `.env` 文件
- **示例**:
  ```bash
  SECRET_KEY=your-secret-key-here-change-in-production
  DATABASE_URL=postgres://hetu:hetu@hetu-db:5432/hetu
  ```

## 使用场景

### 生产环境部署（CI/CD）
- 使用 `env.template` + GitHub Secrets
- GitHub Actions 自动生成 `.env` 文件
- 无需手动操作

### 本地开发
- 复制 `env.example` 为 `.env`
- 根据实际情况修改值
- 手动配置

## 建议

**保留两个文件**，因为：
1. `env.template` 用于自动化部署
2. `env.example` 用于开发者参考和本地开发
3. 两者互补，满足不同场景需求

