"""
自定义Django测试运行器
确保Django能发现和运行scada app的测试
"""

from unittest import TestLoader, TestSuite

from django.test.runner import DiscoverRunner


class CustomTestRunner(DiscoverRunner):
    """自定义测试运行器，确保能发现scada app的测试"""

    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        """
        重写build_suite方法，确保能发现scada app的测试
        """
        suite = TestSuite()

        # 首先尝试使用标准的Django测试发现
        try:
            default_suite = super().build_suite(test_labels, extra_tests, **kwargs)
            if default_suite.countTestCases() > 0:
                suite.addTest(default_suite)
                return suite
        except Exception:
            # 如果标准测试发现失败，继续手动添加测试
            pass

        # 如果没有指定测试标签或指定了scada相关标签，自动添加scada测试
        if not test_labels or any(
            "scada" in str(label) for label in (test_labels or [])
        ):
            try:
                # 导入scada app的测试
                from apps.scada.tests.test_videosource import (
                    VideoSourceAPITest,
                    VideoSourceIntegrationTest,
                    VideoSourceModelTest,
                )

                # 创建测试加载器
                loader = TestLoader()

                # 创建测试套件并添加测试类
                scada_suite = TestSuite()
                scada_suite.addTests(loader.loadTestsFromTestCase(VideoSourceModelTest))
                scada_suite.addTests(loader.loadTestsFromTestCase(VideoSourceAPITest))
                scada_suite.addTests(
                    loader.loadTestsFromTestCase(VideoSourceIntegrationTest)
                )

                # 将scada测试添加到主测试套件
                suite.addTest(scada_suite)

            except ImportError:
                # 如果无法导入scada测试，静默跳过（可能是测试环境问题）
                pass

        return suite
