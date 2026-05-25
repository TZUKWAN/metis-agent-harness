"""Evidence and claim schema primitives."""

from __future__ import annotations

from enum import StrEnum


class EvidenceSourceType(StrEnum):
    USER_INPUT = "user_input"
    FILE = "file"
    TOOL_OUTPUT = "tool_output"
    COMMAND = "command"
    WEB = "web"
    ARTIFACT = "artifact"
    MODEL_INFERENCE = "model_inference"
    GIT = "git"
    TEST = "test"
    API = "api"


class EvidenceStrength(StrEnum):
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


class CompletionClaim(StrEnum):
    GENERATED = "已生成"
    RAN = "已运行"
    TESTED = "已测试"
    UPLOADED = "已上传"
    FIXED = "已修复"


SOURCE_TYPES = {item.value for item in EvidenceSourceType}
