# Iteration 084: Capped Schema Repair Template Prompt Context

日期：2026-05-25

## 本轮目标

Iteration 078 把 `schema_repair_argument_templates` 注入 targeted eval prompt。这个方向是正确的，但存在一个新风险：如果一个 repair task 携带大量 hint details，prompt 会被模板 JSON 撑大。

对 9B/flash 模型来说，过多模板会带来两个问题：

1. 上下文噪声增加，模型更难抓住核心修复目标。
2. prompt token 被诊断元数据占用，留给任务执行的空间变少。

本轮目标是为 prompt-visible schema repair templates 增加稳定排序、数量上限和溢出摘要。

## 已完成变更

1. 新增常量：

```python
MAX_PROMPT_SCHEMA_REPAIR_ARGUMENT_TEMPLATES = 5
```

2. `_eval_stub_argument_template_context()` 现在会：

- 对模板稳定排序；
- 只把前 5 个模板完整写入 prompt；
- 写明 `showing N of M templates`；
- 如果有溢出，写入 omitted 数量；
- 用 `hint_type@schema_path` 摘要保留被省略模板的痕迹。

3. 新增排序函数 `_prompt_argument_template_sort_key()`。

排序优先级：

1. 有 `corrected_arguments` 的模板优先。
2. `tool_name`。
3. `schema_path`。
4. `hint_type`。
5. `schema_keyword`。

4. 新增测试：

- 7 个模板时 prompt 只展示 5 个；
- prompt 包含 `showing 5 of 7 templates`；
- prompt 包含 omitted 摘要；
- 有 corrected arguments 的模板优先；
- lower-priority template 不以完整 JSON 进入 prompt，但在 omitted 摘要中可见。

## 对 Metis Harness 的意义

高质量 harness 不只是把更多信息塞给模型，而是要控制信息密度。对小模型尤其如此。

这一轮让 targeted eval prompt 更适合 9B/flash 模型：

1. 关键修复模板完整展示。
2. 次要模板保留摘要，不完全丢失诊断线索。
3. prompt 结构更稳定，便于比较和回归。
4. 避免 schema repair event 暴涨时 prompt 失控。

## 当前限制

1. 上限 `5` 是静态常量，还不能按模型 profile 调整。
2. 排序策略只看模板结构，没有读取实际 failure frequency。
3. 溢出摘要仍可能较长，后续需要进一步压缩。
4. 没有 token-level budget estimator。
5. 没有把 omitted 模板作为单独 fixture 附件给 runner。

## 下一步任务

1. suite-local/custom tool schema 接入 placeholder 生成。
2. release gate 增加 unversioned suite 策略。
3. validation report 增加 suite schema snapshot id/hash。
4. 为 suite version/migration 增加专用异常与诊断码。
5. prompt context 增加 profile-aware budget。

## 验证结果

- `python -m pytest tests\unit\test_eval_compare.py -q`
  - 结果：35 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py -q`
  - 结果：130 passed
- `python -m pytest -q`
  - 结果：318 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
