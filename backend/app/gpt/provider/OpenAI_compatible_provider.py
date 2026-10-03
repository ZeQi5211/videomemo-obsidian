from typing import Optional, Union, Tuple

from app.utils.logger import get_logger
from app.utils.openai_client import build_openai_client

logging= get_logger(__name__)
class OpenAICompatibleProvider:
    def __init__(self, api_key: str, base_url: str, model: Union[str, None]=None):
        # build_openai_client：注入全局代理 + 校验 api_key 非空
        self.client = build_openai_client(api_key, base_url, key_label="模型供应商的 API Key")
        self.model = model

    @property
    def get_client(self):
        return self.client

    @staticmethod
    def test_connection(api_key: str, base_url: str, model: str) -> Tuple[bool, str]:
        """发一条最小化 chat completion 验证 key / base_url / model 三方都通。

        为什么不用 client.models.list()：
          - 部分代理 / 自建供应商不实现 /v1/models（如某些 OpenAI 兼容网关）
          - 部分供应商 key 在没有 inference 权限时 /v1/models 仍返回 200
        最终用户跑的就是 chat.completions.create，所以直接测它最忠实。
        max_tokens=1 + temperature=0 让请求开销 < 0.0001 美元、延迟 < 2s。

        返回 (ok, error_detail)：
          - ok=True 时 error_detail 为空字符串；
          - ok=False 时 error_detail 为供应商返回的真实原因（如 402 余额不足、
            401 key 无效、模型不存在等），供上层原样透传给前端，
            避免笼统的「API / API 地址不正确」让用户无从排查。
        """
        try:
            client = build_openai_client(
                api_key, base_url, key_label="模型供应商的 API Key", timeout=15.0,
            )
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                temperature=0,
            )
            logging.info(f"连通性测试成功（model={model}）")
            return True, ""
        except Exception as e:
            detail = OpenAICompatibleProvider._extract_error_detail(e)
            logging.warning(f"连通性测试失败（model={model}）：{detail}")
            return False, detail

    @staticmethod
    def _extract_error_detail(e: Exception) -> str:
        """从异常里尽量提取供应商返回的真实错误信息，便于用户自行排查。"""
        status = getattr(e, "status_code", None)
        body = getattr(e, "body", None)
        detail = None
        if isinstance(body, dict):
            # 兼容 {message: ...} 与 {error: {message: ...}} 两种返回结构
            msg = body.get("message")
            if not msg and isinstance(body.get("error"), dict):
                msg = body["error"].get("message")
            if msg:
                detail = msg
            elif body.get("detail"):
                detail = body.get("detail")
        if not detail:
            # openai SDK 的 message 形如 'Error code: 402 - {"code":30001,...}'
            raw = getattr(e, "message", None) or str(e)
            if isinstance(raw, str) and " - " in raw:
                detail = raw.split(" - ", 1)[1].strip().strip("'\"")
            else:
                detail = raw
        detail = str(detail or "未知错误").strip()[:500]
        if status:
            return f"HTTP {status}: {detail}"
        return detail