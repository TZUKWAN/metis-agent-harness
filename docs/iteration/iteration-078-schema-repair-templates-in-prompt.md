# Iteration 078: Schema Repair Templates In Prompt

日期：2026-05-25

## 本轮目标

Iteration 077 已经能生成 schema-compatible corrected arguments，并把它们转成 `required_tool_arguments`。但这些信息主要存在于 metadata 和 suite gate 中，真实模型执行 targeted eval 时，prompt 里只看到 hint type、schema path 和 keyword。

这会造成一个问题：小模型知道“发生过 schema repair”，但不知道这次 eval 要复现的具体 failure shape 是什么，也不知道 corrected call 应该长成什么样。

本轮目标是把 `schema_repair_argument_templates` 注入 targeted eval prompt，让模型在运行时看到结构化的错误参数和修正参数对照。

## 已完成变更

1. `_eval_stub_for_repair_task()` 会把已生成的 `argument_templates` 传给 `_eval_stub_prompt()`。

2. `_eval_stub_prompt()` 新增 `argument_templates` 参数。

3. 新增 `_eval_stub_argument_template_context()`，把每个模板压缩成确定性的 JSON 片段写入 prompt。

每个片段包含：

- `tool`
- `hint_type`
- `schema_path`
- `malformed_arguments`
- `corrected_arguments`

4. prompt 明确说明：

- 这些模板是 exact failure-shape targets；
- placeholder 是 schema-compatible template；
- placeholder 不是业务数据。

5. 单元测试新增断言，确认 prompt 中出现：

- `corrected_arguments.path = outputs/metis-placeholder.txt`
- `malformed_arguments.url = <unsupported url>`
- `corrected_arguments.command = ["metis-placeholder-command_item"]`

## 当前 Prompt 形态

生成后的 prompt 会包含三层信息：

1. repair task 原因、cluster 和 critical event。
2. schema repair hint types、paths、keywords。
3. schema repair argument templates。

这样 targeted eval 的信息链路变成：

```text
comparison regression
-> repair task
-> critical schema.repair_hint event
-> typed hint details
-> schema-compatible argument template
-> prompt-visible failure-shape target
-> required_tool_arguments gate
```

## 对 9B/Flash 模型的意义

小模型在复杂工具调用里失败，很多时候不是因为不知道目标，而是因为缺少足够具体的中间约束。只告诉它“修复 schema 错误”，太抽象；告诉它“不要传 url，必须传 path，path 的目标结构是这个”，成功率会更高。

这一轮把隐式 metadata 转成显式 prompt context，让 harness 对小模型承担更多执行责任：

1. 降低模型自己推断 schema repair 形状的负担。
2. 把 eval 目标从抽象描述变成可执行对照。
3. 让 prompt、metadata、gate 三者指向同一组参数事实。
4. 避免模型通过泛化回答绕过具体工具调用要求。

## 当前限制

1. prompt 注入仍是纯文本 JSON 片段，没有独立 fixture 文件。
2. prompt 还没有按 token budget 做压缩策略；大量 hint event 时可能过长。
3. 模板没有区分“必须复现 malformed call 后再修复”和“只需最终 corrected call 达标”。
4. placeholder 仍主要来自内置工具 schema，custom tool schema 尚未接入。
5. real 9B provider eval 尚未运行这些 prompt-visible hint-derived tasks。

## 下一步任务

1. 给 materialized targeted suite 增加 schema version。
2. 为 prompt template context 增加数量限制、排序策略和溢出摘要。
3. 支持 suite-local/custom tool schema 注入 placeholder 生成。
4. 增加 eval runner 对 malformed/corrected template 的专用 metrics。
5. 把 hint-derived tasks 接入真实 9B provider eval。

## 验证结果

- `python -m pytest tests\unit\test_eval_compare.py -q`
  - 结果：34 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`
  - 结果：90 passed
- `python -m pytest -q`
  - 结果：312 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
