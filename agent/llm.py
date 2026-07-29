"""LLM 调用层 — 通过 openclaw CLI 调用模型。

所有对外 AI 调用统一走这里。使用 subprocess + 参数列表 (shell=False)，
防止职位文本中的特殊字符被 shell 解析。

参考 job-research agent/llm.py。
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Optional


def _cli_infer(
    prompt: str,
    model: str,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """通过 openclaw CLI 调用模型，返回原始输出文本。"""
    import shutil
    openclaw = shutil.which("openclaw") or shutil.which("openclaw.cmd")
    if not openclaw:
        raise RuntimeError("openclaw 未安装")

    cmd = [
        openclaw, "infer", "model", "run",
        "--model", model,
        "--prompt", prompt,
        "--json",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        shell=False,
        env={
            **os.environ,
            "OPENCLAW_INFER_TEMPERATURE": str(temperature),
            "OPENCLAW_INFER_MAX_TOKENS": str(max_tokens),
        },
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"模型调用失败 ({model}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _parse_output(raw: str) -> str:
    """解析 CLI JSON 输出，提取纯文本。

    openclaw --json 返回:
    {"ok": true, "capability": "model.run", "outputs": [{"text": "...", ...}]}
    """
    import re
    # 清理 ANSI 转义序列
    cleaned = re.sub(r"\x1b\[[0-9;]*m", "", raw)

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            outputs = data.get("outputs", [])
            if outputs and isinstance(outputs[0], dict):
                return outputs[0].get("text", cleaned)
            return data.get("text", cleaned)
        return cleaned
    except json.JSONDecodeError:
        # 不是 JSON — 可能 openclaw --json 未生效，直接返回清理后的文本
        # 去除常见的日志行前缀
        lines = cleaned.split("\n")
        text_lines = [
            l for l in lines
            if not l.startswith("[") and "provider-transport" not in l
            and "model-fetch" not in l and "model.run" not in l
            and not l.startswith("provider:") and not l.startswith("model:")
            and not l.startswith("outputs:") and not l.startswith("transport:")
        ]
        return "\n".join(text_lines).strip() or cleaned


def chat(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """通用模型调用，返回纯文本。

    Args:
        prompt: 提示词
        model: 模型名，默认 "opencode-go/deepseek-v4-flash"
        temperature: 生成温度
        max_tokens: 最大生成 token 数

    Returns:
        模型回复文本
    """
    model = model or "opencode-go/deepseek-v4-flash"
    raw = _cli_infer(prompt, model, temperature, max_tokens)
    return _parse_output(raw)


def chat_json(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.3,
) -> dict:
    """调用模型并解析返回的 JSON。"""
    import re
    result = chat(prompt, model, temperature)
    result = result.strip()
    # 清理 ANSI 码（可能从 chat 的 fallback 路径带入）
    result = re.sub(r"\x1b\[[0-9;]*m", "", result)
    # 去除可能的 markdown 代码块标记
    if result.startswith("```"):
        lines = result.split("\n")
        result = "\n".join(l for l in lines if not l.startswith("```"))
    # 尝试找到 JSON 块
    # 有时模型会在 JSON 前后加说明文字
    json_start = result.find("{")
    if json_start != -1:
        result = result[json_start:]
    json_end = result.rfind("}")
    if json_end != -1:
        result = result[: json_end + 1]
    return json.loads(result)
