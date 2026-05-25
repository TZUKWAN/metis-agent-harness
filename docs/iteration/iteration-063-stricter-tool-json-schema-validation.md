# Iteration 063: Stricter Tool JSON Schema Validation

日期：2026-05-25

## 本轮目标

本轮继续处理 harness 层面的确定性可靠性问题：工具调用参数不能只靠模型“尽量写对”，必须由工具执行前的 schema guardrail 严格验证。

上一轮已经让 eval suite 的 `required_tool_arguments` 可以和工具 schema 对齐。本轮把同一条线推进到运行时工具调用：扩大 `ToolArgumentSchemaValidator` 支持的 JSON Schema 子集，并收紧内置工具 schema，减少 9B/flash 小模型常见的参数漂移。

## 外部参考结论

OpenAI Agents SDK 的 guardrails 文档强调，涉及工具调用的流程需要 tool-level guardrail，因为 input/output guardrail 只覆盖工作流边界，无法替代每一次函数工具调用前后的检查。

JSON Schema 官方说明也明确：`properties` 只定义已知字段的校验方式，默认不会禁止额外字段；如果要拒绝额外字段，需要使用 `additionalProperties: false` 或用 schema 校验额外字段。

对 Metis 的结论是：工具 schema 必须足够明确，并且 dispatcher 前置校验必须支持足够多的基础 JSON Schema 约束，否则小模型传入错误参数时会漏过执行前防线。

## 已完成变更

1. `ToolArgumentSchemaValidator` 新增字符串约束：
   - `minLength`
   - `maxLength`
   - `pattern`

2. `ToolArgumentSchemaValidator` 新增数值约束：
   - `minimum`
   - `maximum`
   - `exclusiveMinimum`
   - `exclusiveMaximum`

3. `ToolArgumentSchemaValidator` 新增数组约束：
   - `minItems`
   - `maxItems`

4. `ToolArgumentSchemaValidator` 新增对象额外字段约束：
   - `additionalProperties: false`
   - `additionalProperties: { ...schema... }`
   - `patternProperties`

5. `oneOf` 改为严格语义。
   - 之前是“任一分支通过即可”，更接近 `anyOf`。
   - 现在要求恰好一个分支匹配。
   - 没有分支匹配时会保留各分支错误摘要，便于后续 repair feedback。
   - 多个分支同时匹配时会明确报错。

6. 内置工具 schema 更严格：
   - `read_file`：关闭额外参数，`path`/`encoding` 增加非空字符串约束。
   - `write_file`：关闭额外参数，`path`/`encoding` 增加非空字符串约束。
   - `run_shell`：关闭额外参数，`command` 非空，`timeout` 限定 1 到 3600。
   - `run_command`：关闭额外参数，命令字符串/数组非空，`timeout` 限定 1 到 3600。
   - `run_test`：关闭额外参数，命令字符串/数组非空，`timeout` 限定 1 到 3600。
   - `encoding` 收紧为 `utf-8` / `utf-8-sig`，避免文件 handler 才暴露编码错误。

## 新增测试覆盖

1. `additionalProperties: false` 能拒绝额外字段。
2. `additionalProperties` 为 schema 时，额外字段值会按该 schema 校验。
3. `patternProperties` 可以按字段名模式绑定子 schema。
4. 字符串长度、字符串正则、数值范围、排他数值范围、数组长度均可被校验。
5. dispatcher 在 handler 执行前阻断 closed schema 的额外参数，确保错误工具调用不会进入副作用执行阶段。
6. `oneOf` 多分支同时匹配时会失败。
7. `oneOf` 零分支匹配时会输出分支错误摘要。
8. 内置 `run_command` 会在执行前阻断空命令数组和非法 timeout。
9. 内置 `read_file` 会在执行前阻断未知参数和非法 encoding。

## 对 9B/flash 小模型的价值

小模型在工具调用中容易出现以下问题：

1. 多写一个看似合理但工具不支持的参数。
2. 把 timeout 写成字符串、0、负数或过大数值。
3. 传空命令、空路径、空数组。
4. 误把搜索 URL、业务对象或解释性字段塞进文件工具。

本轮改动让这些错误更早、更加确定性地失败，并且失败会形成结构化 schema error，后续 repair loop 可以基于具体错误反馈让模型重试。

## 剩余问题

1. 当前 validator 仍未支持完整 JSON Schema：
   - `allOf`
   - `anyOf`
   - `not`
   - `const`
   - `multipleOf`
   - `uniqueItems`
   - `minProperties`
   - `maxProperties`
   - `dependentRequired`

2. `oneOf` 失败信息已经比上一轮更具体，但仍然没有计算“最接近分支”，后续可以把最少错误分支作为优先 repair hint。

3. 内置工具 schema 仍然偏少，缺少专门面向场景 agent 的安全工具模板，例如：
   - 只读检索工具
   - 结构化写文件工具
   - 受控测试工具
   - 交付物校验工具
   - 任务规划/状态更新工具

4. 还没有专门的 eval 任务验证“额外参数被拒绝后，小模型能根据 repair feedback 删除多余参数并成功重试”。

## 验证结果

- `python -m pytest tests\unit\test_tool_schema_validator.py tests\unit\test_tools.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`
  - 结果：45 passed
- `python -m compileall -q metis`
  - 结果：通过
