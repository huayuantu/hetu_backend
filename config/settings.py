"""
Django settings for hetu project.

Generated by 'django-admin startproject' using Django 4.2.3.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""
from pathlib import Path
import environ
import os

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False)
)

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent

environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

APPS_DIR = BASE_DIR / "apps"

# 密钥
SECRET_KEY = env("SECRET_KEY")

# 调试模式
DEBUG = env("DEBUG")

# 允许本地和Docker环境
ALLOWED_HOSTS = ["host.docker.internal", "localhost", "127.0.0.1", "hetu-api"]

# 安装的应用列表
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "casbin_adapter.apps.CasbinAdapterConfig",
    "apps.scada",
    "apps.sys",
]

# 安装的中间件
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

# 根路由
ROOT_URLCONF = "config.urls"

# 采用默认的模版配置
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# 使用pg13数据库
DATABASES = {"default": env.db_url()}

# 采用默认内存缓存
CACHES = {"default": env.cache_url()}

# 不使用国际化
USE_I18N = False

# 启用时区
USE_TZ = True

# 采用标准UTC
TIME_ZONE = "UTC"

# 静态文件
STATIC_URL = "static/"

# 默认使用的自增ID类型
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Casbin模型配置
CASBIN_MODEL = str(BASE_DIR / "apps/sys/casbin.conf")

# API分页默认值
PAGINATION_PER_PAGE = 20

# Prometheus接口配置
PROMETHEUS_URL = env("PROMETHEUS_URL")

# 推送地址
PUSHGATEWAY_URL = env("PUSHGATEWAY_URL")

# Prometheus发现目录
PROMETHEUS_RULES_DIR = env("PROMETHEUS_RULES_DIR")

# supervisor接口地址
SUPERVISOR_XMLRPC_URL = env("SUPERVISOR_XMLRPC_URL")

# Exporter命令
SUPERVISOR_COLLECTOR_COMMAND = env("SUPERVISOR_COLLECTOR_COMMAND")

# Exporter起始端口
SUPERVISOR_COLLECTOR_PORT = 20000

# Exporter监听地址
SUPERVISOR_COLLECTOR_HOST = "0.0.0.0"

# Exporter访问地址
SUPERVISOR_COLLECTOR_ADVERTISE = env("SUPERVISOR_COLLECTOR_ADVERTISE")

# supervisor任务配置目录
SUPERVISOR_COLLECTOR_DIR =  env("SUPERVISOR_COLLECTOR_DIR")
