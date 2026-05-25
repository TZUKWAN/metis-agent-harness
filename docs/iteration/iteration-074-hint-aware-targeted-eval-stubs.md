# Iteration 074: Hint-Aware Targeted Eval Stubs

日期：2026-05-25

## 本轮目标

Iteration 073 已经让 repair task 继承 `schema_repair_hint_events`。本轮继续把这份 payload 用起来，让 targeted eval stub 不再只是泛化的 schema repair stub，而是能生成 hint-aware eval skeleton。

目标是把诊断链路推进到：

```text
schema.repair_hint event
-> diagnosis schema_repair_hint_events
-> repair task schema_repair_hint_events
-> targeted eval stub with hint taxonomy
-> materialized targeted eval suite
```

## 已完成变更

1. `build_eval_stubs_from_repair_tasks()` 现在会从 `schema_repair_hint_events` 提取：

   - `schema_repair_hint_types`
   - `schema_repair_hint_paths`
   - `schema_repair_hint_keywords`

2. targeted eval stub 会保留原始 `schema_repair_hint_events`。

3. schema hint 相关 stub 的 prompt 会包含 hint context：

   - hint types
   - schema paths
   - schema keywords

4. schema hint 相关 stub 自动增加 hint-aware gates：

   - `min_schema_repair_hint_successes=1`
   - `max_schema_repair_hint_failures=0`

5. `suggested_assertion` 会从泛化 schema repair 升级为具体 hint type recovery：

   - `Schema repair hint recovery succeeds for hint types add_required_property with no unrecovered hint failures.`

6. `eval_stubs_to_markdown()` 展示 schema repair hint types。

7. `materialize_eval_suite_from_stubs()` 保留：

   - `schema_repair_hint_events`
   - `schema_repair_hint_types`

## 对 Metis Harness 的意义

这一轮把“失败诊断”真正接到了“回归评测生成”。

对小模型 harness 来说，这是关键能力：

1. 失败不是只留在人读报告里。
2. 失败会变成 repair task。
3. repair task 会变成 targeted eval stub。
4. stub 会携带具体 hint taxonomy。
5. eval gate 会检查 hint-driven recovery，而不是只检查普通 schema repair。

这让 Metis 可以逐步积累小模型最常失败的 schema hint 类型，并把它们转成稳定回归任务。

## 当前限制

1. stub 还没有自动生成 malformed argument payload。
2. stub 还没有自动生成 corrected argument payload。
3. materialized suite 还需要人工补具体 prompt，才能跑真实 9B/flash 模型。
4. hint type 到工具参数模板的映射还没有建立。

## 下一步任务

1. 从 `schema_repair_hint_details` 推断 malformed/corrected 参数模板。
2. 为 `add_required_property`、`remove_additional_property`、`increase_array_items` 建第一批模板。
3. materialized eval suite 增加 hint-aware task spec metadata。
4. real small-model eval suite 增加由 hint-aware stub 转化来的真实任务。

## 验证结果

- `python -m pytest tests\unit\test_eval_compare.py -q`
  - 结果：33 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py -q`
  - 结果：81 passed
- `python -m pytest -q`
  - 结果：311 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
