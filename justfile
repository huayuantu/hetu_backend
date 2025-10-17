# Django项目命令集合

# 默认命令
default:
    @just --list

# 启动开发服务器
dev:
    python manage.py runserver

# 启动开发服务器（指定端口）
dev-port port:
    python manage.py runserver {{port}}

# 启动生产服务器
prod:
    gunicorn config.wsgi:application -c gunicorn_config.py

# 数据库迁移
migrate:
    python manage.py makemigrations
    python manage.py migrate

# 创建超级用户
createsuperuser:
    python manage.py createsuperuser

# 收集静态文件
collectstatic:
    python manage.py collectstatic --noinput

# 运行测试
test:
    python manage.py test

# 运行测试（指定应用）
test-app app:
    python manage.py test {{app}}

# 代码格式检查（ruff）
check:
    ruff check .

# 代码格式修复（ruff）
fix:
    ruff check --fix .

# 代码格式检查（ruff，包含格式化）
format:
    ruff format .

# 代码质量检查（ruff + 格式化）
lint: check format

# 安装依赖
install:
    pip install -r requirements.txt

# 安装开发依赖
install-dev:
    pip install -r requirements-dev.txt

# 安全更新依赖
update-deps:
    pip install --upgrade pip
    pip install --upgrade -r requirements.txt

# 清理Python缓存
clean:
    find . -type f -name "*.pyc" -delete
    find . -type d -name "__pycache__" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} +

# 数据库重置（危险操作）
reset-db:
    @echo "⚠️  这将删除所有数据！"
    @echo "确认请输入: yes"
    @read -p "确认请输入: yes" input
    @if [ "$$input" = "yes" ]; then \
        python manage.py flush --noinput; \
        echo "数据库已重置"; \
    else \
        echo "操作已取消"; \
    fi

# 查看项目状态
status:
    @echo "📊 项目状态:"
    @echo "Python版本: $(python --version)"
    @echo "Django版本: $(python -c "import django; print(django.get_version())")"
    @echo "当前分支: $(git branch --show-current 2>/dev/null || echo '未在git仓库中')"

# 帮助信息
help:
    @echo "🚀 Django项目命令帮助:"
    @echo ""
    @echo "开发命令:"
    @echo "  just dev              - 启动开发服务器"
    @echo "  just dev-port <port>  - 启动开发服务器（指定端口）"
    @echo "  just migrate          - 数据库迁移"
    @echo "  just test             - 运行测试"
    @echo ""
    @echo "代码质量:"
    @echo "  just check            - 代码格式检查"
    @echo "  just fix              - 代码格式修复"
    @echo "  just format           - 代码格式化"
    @echo "  just lint             - 完整代码质量检查"
    @echo ""
    @echo "部署命令:"
    @echo "  just prod             - 启动生产服务器"
    @echo "  just collectstatic    - 收集静态文件"
    @echo ""
    @echo "维护命令:"
    @echo "  just clean            - 清理缓存文件"
    @echo "  just status           - 查看项目状态"
    @echo "  just help             - 显示此帮助信息"
