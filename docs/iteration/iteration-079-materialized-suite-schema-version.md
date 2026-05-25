# Iteration 079: Materialized Suite Schema Version

日期：2026-05-25

## 本轮目标

Iteration 078 已经把 schema repair argument templates 注入 targeted eval prompt。下一步必须让 materialized targeted suite 的格式可追踪、可验证、可演进。

当前 validator 已经支持读取 `schema_version`，但 `materialize_eval_suite_from_stubs()` 生成的 suite 没有写版本号。这会导致一个隐性风险：同一类 generated suite 未来增加字段、改变 task wrapper 或改变 gate 语义时，runner 和 validator 无法区分老格式和新格式。

本轮目标是让 materialized targeted suite 从源头写入 schema version，并让 Markdown、JSON 和测试都能证明这一点。

## 已完成变更

1. 新增常量：

```python
MATERIALIZED_TARGETED_EVAL_SUITE_SCHEMA_VERSION = "1"
```

2. `materialize_eval_suite_from_stubs()` 生成的 suite 顶层新增：

```json
{
  "schema_version": "1"
}
```

3. `eval_suite_to_markdown()` 顶部会展示：

```text
Schema version: 1
```

4. 单元测试新增断言：

- 内存中的 suite 有 `schema_version == "1"`。
- Markdown 输出展示 `Schema version: 1`。
- 写盘后的 `targeted-eval-suite.json` 保留 `schema_version == "1"`。

## 对 Metis Harness 的意义

Metis 的目标是长期循环改进，而不是一次性生成一个临时 eval 文件。只要 eval suite 会持续演进，就必须有版本。

这对 9B/flash 模型尤其重要：

1. 小模型能力提升依赖大量回归样本持续积累。
2. 这些样本的结构不能靠隐式约定维持。
3. runner、validator、comparison、repair planner 必须知道自己消费的是哪个 suite schema。
4. schema version 是后续 migration、兼容性检查和历史结果解释的基础。

## 当前版本语义

`schema_version = "1"` 表示当前 materialized targeted suite 的基础结构：

1. 顶层 suite metadata：
   - `suite`
   - `schema_version`
   - `profile`
   - `baseline`
   - `current`
   - `task_count`
   - `tasks`
2. 每个 task entry 包含 repair metadata：
   - source repair task id
   - reason
   - priority
   - owner area
   - cluster keys
   - critical events
   - schema repair hint metadata
   - schema repair argument templates
   - likely source modules
   - suggested assertion
   - verification command
3. 每个 task entry 包含 runner-consumable `task_spec`。

## 当前限制

1. validator 目前只校验 `schema_version` 是字符串，还没有拒绝未知版本。
2. suite runner 目前记录版本到 metadata，但没有按版本执行 migration。
3. 还没有 `schema_version` changelog。
4. 还没有旧 suite 到新 suite 的 migration 工具。
5. 还没有把 version compatibility 写入 release gate。

## 下一步任务

1. validator 增加 supported schema version 检查。
2. runner 增加 version-aware load path，为后续 migration 留接口。
3. 增加 `docs/evals/suite-schema.md`，记录各版本字段语义。
4. prompt argument template context 增加数量限制和溢出摘要。
5. 支持 suite-local/custom tool schema 注入 placeholder 生成。

## 验证结果

- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`
  - 结果：54 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`
  - 结果：90 passed
- `python -m pytest -q`
  - 结果：312 passed, 4 skipped
- `python -m compileall -q metis`
  - 结果：通过
