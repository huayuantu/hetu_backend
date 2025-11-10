"""
CORS 中间件
处理跨域请求的响应头
"""


class CorsMiddleware:
    """简单的 CORS 中间件"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 处理预检请求
        if request.method == "OPTIONS":
            from django.http import JsonResponse

            response = JsonResponse({})
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
            response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
            response["Access-Control-Max-Age"] = "86400"
            return response

        # 处理正常请求
        response = self.get_response(request)

        # 添加 CORS 响应头
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"

        return response

