# Iteration 080: Supported Suite Schema Version Validation

日期：2026-05-25

## 本轮目标

Iteration 079 已经让 materialized targeted suite 写入 `schema_version: "1"`。但 validator 之前只检查 `schema_version` 是否为字符串，没有判断这个版本是否真的被当前 harness 支持。

这会导致一个风险：未来出现 `schema_version: "2"` 或其他未知格式时，当前 runner 可能继续加载并运行，最后把格式不兼容误判成模型失败或 harness 失败。

本轮目标是让 validator 具备 supported schema version 检查。

## 外部参考结论

本轮检索了 eval dataset 和 schema version 相关资料，关键结论：

1. OpenAI Evals 的 custom data source 明确依赖 schema 定义 eval 数据形状。
2. Microsoft agent evaluation dataset 把 `schemaVersion` 和 `items` 作为最小有效数据集结构，并强调 major version 内向后兼容。
3. JSON/schema registry 领域的通用做法是显式声明版本，并在消费端执行兼容性判断。

对 Metis 来说，这意味着 eval suite 不能只“有版本字段”，还必须让消费端知道哪些版本可被当前代码安全处理。

## 已完成变更

1. `suite_validation.py` 新增：

```python
SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS = frozenset({"1"})
```

2. `_validate_top_level()` 增加版本支持检查：

- 缺失 `schema_version`：保持 warning，用于兼容旧手写 suite。
- 非字符串 `schema_version`：error。
- 字符串但不在 supported set 中：error。

3. validation report 新增：

```json
{
  "supported_schema_versions": ["1"]
}
```

4. Markdown validation report 新增：

```text
Supported schema versions: 1
```

5. 新增测试：

- valid suite 会报告 `schema_version == "1"`。
- valid suite 会报告 `supported_schema_versions == ["1"]`。
- `schema_version == "2"` 会被拒绝并给出明确错误：

```text
Unsupported schema_version: 2. Supported versions: 1.
```

## 对 Metis Harness 的意义

Metis 的 eval suite 是长期迭代资产。它不只是测试文件，而是：

1. 失败样本的沉淀。
2. 9B/flash 模型能力边界的测量工具。
3. harness 改动是否退化的判断标准。
4. 未来自动 repair plan 和 regression gate 的输入。

因此 suite 格式必须可治理。supported version validation 能让不兼容在运行前暴露，而不是等模型跑完之后才通过异常指标体现。

## 当前限制

1. validator 还没有 migration 机制。
2. runner 还没有 version-aware loader。
3. schema version 仍只有一行常量，没有独立 schema 文档。
4. 缺失版本仍是 warning；未来 release gate 可能需要把 unversioned suite 升级为 error。
5. 没有区分 stable version、deprecated version、experimental version。

## 下一步任务

1. 新增 `docs/evals/suite-schema.md`，记录 schema version 1 的字段语义。
2. runner 增加 version-aware load path，为 migration 留接口。
3. prompt argument template context 增加数量限制、排序策略和溢出摘要。
4. suite-local/custom tool schema 接入 placeholder 生成。
5. release gate 增加 unversioned suite 策略。

## 验证结果

- `python -m pytest tests\unit\test_eval_suite_validation.py -q`
  - 结果：13 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`
  - 结果：91 passed
- `python -m pytest -q`
  - 结果：313 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
