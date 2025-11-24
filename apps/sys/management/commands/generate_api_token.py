"""生成API Token管理命令（独立token，不依赖用户账号）"""

from datetime import UTC, datetime, timedelta

from django.core.management.base import BaseCommand

from apps.sys.utils import generate_api_token


class Command(BaseCommand):
    help = "生成独立的API Token（不依赖Django用户账号）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--expires-days",
            type=int,
            default=365,
            help="Token过期天数（默认: 365天）",
        )
        parser.add_argument(
            "--output-env",
            action="store_true",
            help="输出环境变量配置格式（用于data-crawler项目的.env文件）",
        )

    def handle(self, *args, **options):
        expires_days = options["expires_days"]
        output_env = options.get("output_env", False)

        # 生成独立的API token（不依赖用户账号）
        expires = datetime.now(UTC) + timedelta(days=expires_days)
        token = generate_api_token(expires)

        if output_env:
            # 输出环境变量配置格式
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("✓ API Token生成成功"))
            self.stdout.write("=" * 60)
            self.stdout.write("\n# 将以下内容添加到 data-crawler 项目的 .env 文件中：\n")
            self.stdout.write(f"DATA_CRAWLER_API_TOKEN={token}\n")
            self.stdout.write("=" * 60)
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠ 重要提示："
                    f"\n1. 这是一个独立的API token，不依赖Django用户账号"
                    f"\n2. 请将上述环境变量添加到 data-crawler 项目的 .env 文件中"
                    f"\n3. Token过期时间: {expires.isoformat()}"
                    f"\n4. Token过期后需要重新生成"
                )
            )
        else:
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("✓ API Token生成成功"))
            self.stdout.write("=" * 60)
            self.stdout.write(f"\nToken过期时间: {expires.isoformat()}")
            self.stdout.write(f"\nToken (请妥善保管):\n{token}\n")
            self.stdout.write("=" * 60)
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠ 重要提示："
                    "\n1. 这是一个独立的API token，不依赖Django用户账号"
                    "\n2. 请将token保存到安全的地方"
                    "\n3. 建议通过环境变量 DATA_CRAWLER_API_TOKEN 配置"
                    "\n4. 使用 --output-env 参数可以直接输出环境变量配置格式"
                    "\n5. Token过期后需要重新生成"
                )
            )

