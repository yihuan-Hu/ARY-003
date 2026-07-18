"""
人员 D 测试：GitHub OAuth（离线测试）
"""
import json
import pytest

from tests.conftest import _create_user, _login


def _get_json(response):
    return json.loads(response.data)


class TestGitHubOAuth:
    """GitHub OAuth（本地环境测试）"""

    def test_github_not_configured(self, client):
        """GitHub OAuth 未配置时返回错误（ValidationError → 400）"""
        resp = client.get("/api/v1/auth/github")
        assert resp.status_code == 400

    def test_github_callback_no_code(self, client):
        """GitHub 回调缺少 code（ValidationError → 400）"""
        resp = client.get("/api/v1/auth/github/callback")
        assert resp.status_code == 400
