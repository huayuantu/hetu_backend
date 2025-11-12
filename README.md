# HeTu Backend 🏭

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Django Version](https://img.shields.io/badge/Django-4.2+-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 📖 项目简介

**养殖污水处理智慧运营平台后端API** - 基于Django + Django Ninja构建的现代化REST API服务，为养殖污水处理提供全面的智慧运营解决方案。

### 🎯 核心功能

- **📊 SCADA监控**: 实时监控污水处理设备运行状态和数据采集
- **🎥 视频监控**: 集成萤石云和华为IVM视频监控系统
- **📈 数据分析**: 基于Prometheus的指标收集和监控告警
- **👥 用户管理**: 基于Casbin的RBAC权限管理系统
- **📋 运营管理**: 站点管理、设备管理和运营数据统计
- **🔄 消息队列**: 基于MQTT的设备通信和数据同步

## 🛠️ 技术栈

### 核心框架
- **Django 4.2+** - 高性能Web框架
- **Django Ninja** - 现代化REST API框架
- **PostgreSQL** - 关系型数据库
- **Redis** - 缓存和会话存储

### 外部服务集成
- **Prometheus** - 指标收集和监控
- **AlertManager** - 告警管理
- **萤石云API** - 视频监控服务
- **华为IVM** - 工业视频监控
- **阿里云OSS** - 对象存储
- **MQTT** - 物联网消息队列

### 开发工具
- **Just** - 命令运行器，统一项目命令接口
- **uv** - Python 包管理器（快速依赖管理）
- **Gunicorn** - WSGI服务器
- **Supervisor** - 进程管理
- **Docker & Docker Compose** - 容器化部署
- **MyPy & Ruff** - 代码质量检查

### CI/CD
- **GitHub Actions** - 自动化构建和部署
- **Docker Registry** - 容器镜像仓库
- **自动化部署** - 支持多环境部署

## 🚀 快速开始

### 📋 环境要求

- Python 3.12+
- PostgreSQL 13+
- Redis 7+
- Docker & Docker Compose
- [Just](https://github.com/casey/just) - 命令运行器（推荐）

### 🔧 安装步骤

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd hetu_backend
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # 或
   .venv\Scripts\activate     # Windows
   ```

3. **安装依赖**
   ```bash
   # 使用 uv（推荐，更快）
   uv sync
   
   # 或使用 pip
   pip install -e .
   ```

4. **配置环境变量**
   ```bash
   cp env.example .env
   # 编辑 .env 文件，配置数据库和其他服务
   ```

5. **数据库迁移**
   ```bash
   just migrate
   ```

6. **创建超级用户**
   ```bash
   # 使用自定义命令（推荐，需要密码和部门参数）
   python manage.py create_admin <password> <department>
   
   # 或使用 Django 默认命令（交互式）
   just createsuperuser
   ```

7. **启动开发服务器**
   ```bash
   just dev
   # 或指定端口
   just dev-port 8000
   ```

### 🐳 Docker部署

```bash
# 生产环境部署
docker-compose -f docker-compose.prod.yml up -d

# 开发环境部署
docker-compose -f docker-compose.local.yml up -d
```

### 🚀 CI/CD 自动化部署

项目已配置 GitHub Actions 自动化部署，支持通过 Git tag 触发自动构建和部署。

**快速部署**:
1. 配置 GitHub Secrets（参考 `docs/cicd-setup.md`）
2. 创建并推送版本 tag：
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. GitHub Actions 会自动构建 Docker 镜像并部署到服务器

详细说明请参考：
- `docs/cicd-setup.md` - CI/CD 配置文档
- `docs/cicd-quick-reference.md` - 快速参考
- `docs/multi-environment-deployment.md` - 多环境部署指南

## 📁 项目结构

```
hetu_backend/
├── apps/                     # Django应用模块
│   ├── scada/               # SCADA监控模块
│   │   ├── models.py        # 数据模型
│   │   ├── view/            # API视图
│   │   ├── schema/          # Pydantic模式
│   │   ├── utils/           # 工具函数
│   │   ├── script/          # 后台脚本
│   │   └── tests/           # 单元测试
│   └── sys/                 # 系统管理模块
│       ├── models.py        # 用户、角色、权限模型
│       ├── view/            # 管理API
│       ├── rolemanager.py   # 权限管理器
│       └── tests/           # 测试
├── config/                  # 项目配置
│   ├── settings.py          # Django设置
│   ├── urls.py              # URL配置
│   ├── wsgi.py              # WSGI配置
│   └── test_runner.py       # 自定义测试运行器
├── utils/                   # 工具库
│   └── schema/              # API模式定义
├── deploy/                  # 部署配置
│   ├── prometheus/          # Prometheus配置
│   ├── alertmanager/        # 告警管理配置
│   └── supervisor/          # 进程管理配置
├── scripts/                 # 部署脚本
│   ├── deploy.sh            # 部署脚本
│   ├── generate-deploy-configs.sh  # 配置生成脚本
│   └── init-deploy-config.sh        # 配置初始化脚本
├── .github/workflows/       # GitHub Actions 工作流
│   └── deploy.yml           # CI/CD 部署配置
├── docs/                    # 文档目录
│   ├── cicd-setup.md        # CI/CD 配置文档
│   ├── cicd-quick-reference.md  # CI/CD 快速参考
│   └── ...                  # 其他文档
├── env.example              # 环境变量示例文件
├── env.template             # 环境变量模板（用于 CI/CD）
├── docker-compose.prod.yml  # 生产环境 Docker 编排
├── docker-compose.local.yml # 开发环境 Docker 编排
├── Dockerfile               # Docker镜像
├── pyproject.toml           # 项目配置（使用 uv）
├── justfile                 # Just 命令定义
└── manage.py               # Django管理脚本
```

## 📡 API文档

### 🔗 接口地址

- **开发环境**: http://localhost:8000/api/
- **API文档**: http://localhost:8000/api/docs
- **健康检查**: http://localhost:8000/-/healthy

### 📋 主要接口模块

#### SCADA监控模块 (`/api/scada/`)

- **站点管理**: CRUD操作
- **设备监控**: 实时数据采集
- **视频源**: 萤石云/华为IVM集成
- **告警管理**: 阈值设置和告警处理
- **数据图表**: 历史数据可视化

#### 系统管理模块 (`/api/sys/`)

- **用户管理**: 用户注册、登录、权限管理
- **角色权限**: 基于Casbin的RBAC权限系统
- **部门管理**: 组织架构管理
- **菜单管理**: 动态菜单配置
- **文件上传**: 基于阿里云OSS的文件存储

### 🔐 认证方式

- **JWT Token**: Bearer Token认证
- **Casbin权限**: 细粒度的权限控制

## 🗄️ 数据库配置

项目支持多种数据库配置方式：

### 环境变量配置

在 `.env` 文件中设置：

```bash
# SQLite (开发环境)
DATABASE_URL=sqlite:///db.sqlite3

# PostgreSQL (生产环境)
DATABASE_URL=postgresql://username:password@localhost:5432/hetu_db

# MySQL
DATABASE_URL=mysql://username:password@localhost:3306/hetu_db
```

### 数据库迁移

```bash
# 生成迁移文件并执行迁移（推荐）
just migrate

# 或使用传统命令
python manage.py makemigrations
python manage.py migrate

# 显示迁移状态
python manage.py showmigrations
```

## 🧪 测试

### 运行测试

```bash
# 运行所有测试（推荐）
just test

# 运行特定应用的测试
just test-app apps.scada

# 或使用传统命令
python manage.py test
python manage.py test apps.scada

# 运行带覆盖率的测试
coverage run manage.py test
coverage report
```

### 测试结构

- **单元测试**: `apps/*/tests/test_*.py`
- **集成测试**: API端到端测试
- **模型测试**: 数据模型验证
- **视图测试**: API接口测试

## 🚀 部署

### 自动化部署（推荐）

项目已配置 GitHub Actions CI/CD，支持自动化部署：

1. **配置 GitHub Secrets**（参考 `docs/cicd-setup.md`）
2. **创建版本 tag 触发部署**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. GitHub Actions 会自动：
   - 构建 Docker 镜像
   - 推送到镜像仓库
   - 同步配置文件到部署服务器
   - 生成 `.env` 文件
   - 部署服务

详细文档：
- `docs/cicd-setup.md` - 完整配置指南
- `docs/cicd-quick-reference.md` - 快速参考
- `docs/multi-environment-deployment.md` - 多环境部署

### 手动部署

#### 生产环境部署

1. **准备部署服务器**
   ```bash
   # 创建部署目录
   mkdir -p /opt/hetu-backend
   chmod 755 /opt/hetu-backend
   ```

2. **配置环境变量**
   ```bash
   # 在部署服务器上创建 .env 文件
   # 参考 env.example 文件
   ```

3. **构建和启动服务**
   ```bash
   export HETU_VERSION=v1.0.0
   export REGISTRY="your-registry"
   export IMAGE_NAME="your-image-name"
   docker-compose -f docker-compose.prod.yml up -d
   ```

#### Docker Compose 部署

```bash
# 生产环境部署
docker-compose -f docker-compose.prod.yml up -d

# 开发环境部署
docker-compose -f docker-compose.local.yml up -d
```

### 服务说明

部署后的服务地址：
- **API服务**: `http://localhost:8000`
- **Prometheus**: `http://localhost:9090`
- **AlertManager**: `http://localhost:9093`
- **PushGateway**: `http://localhost:9091`
- **PgAdmin**: `http://localhost:5050`

### 监控和日志

- **Prometheus**: 指标收集和监控
- **AlertManager**: 告警通知
- **Supervisor**: 进程监控和管理
- **Gunicorn**: WSGI服务器日志

## 🔧 开发环境设置

### Just 命令工具

项目使用 [Just](https://github.com/casey/just) 作为命令运行器，提供统一的命令接口。

**查看所有可用命令**:
```bash
just
# 或
just help
```

**常用命令**:
```bash
# 开发
just dev              # 启动开发服务器
just dev-port 8000    # 启动开发服务器（指定端口）
just migrate          # 数据库迁移
just test             # 运行测试
just test-app apps.scada  # 运行指定应用的测试

# 代码质量
just check            # 代码格式检查
just fix              # 代码格式修复
just format           # 代码格式化
just lint             # 完整代码质量检查（check + format）

# 部署
just prod             # 启动生产服务器
just collectstatic    # 收集静态文件

# 维护
just clean            # 清理缓存文件
just status           # 查看项目状态
```

### 代码质量工具

```bash
# 使用 Just 命令（推荐）
just lint             # 完整代码质量检查
just check            # 代码格式检查
just format           # 代码格式化

# 或使用传统命令
ruff format .
ruff check .
mypy .
```

### 开发工具

- **Just**: 命令运行器（推荐安装）
- **uv**: Python 包管理器（推荐，更快）
- **VS Code**: 推荐IDE
- **REST Client**: API测试工具
- **PgAdmin**: PostgreSQL管理
- **Redis Commander**: Redis管理

### 安装 Just

```bash
# macOS
brew install just

# Linux
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/bin

# Windows
scoop install just
# 或
choco install just
```

## 🤝 贡献指南

### 开发流程

1. **Fork项目**
2. **创建特性分支**: `git checkout -b feature/new-feature`
3. **提交更改**: `git commit -am 'Add new feature'`
4. **推送分支**: `git push origin feature/new-feature`
5. **创建Pull Request**

### 代码规范

- **PEP 8**: Python代码规范
- **类型提示**: 使用MyPy进行类型检查
- **测试覆盖**: 确保测试覆盖率 > 80%
- **文档**: 更新相关文档

### 提交规范

```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式调整
refactor: 代码重构
test: 测试相关
chore: 构建过程或工具配置更新
```

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 👨‍💻 作者

**Huayuan Tu** - [tuhuayuan@gmail.com](mailto:tuhuayuan@gmail.com)

## 🙏 致谢

感谢所有为这个项目做出贡献的开发者！

---

**养殖污水处理智慧运营平台** - 让智慧运营成为可能 🚀