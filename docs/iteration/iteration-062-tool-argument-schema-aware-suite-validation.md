# Iteration 062: Tool Argument Schema-Aware Suite Validation

日期：2026-05-25

## 本轮目标

本轮处理的问题是：Metis 的通用 eval suite 已经能校验工具名、质量门名称和字段类型，但 `required_tool_arguments` 仍然只校验“结构像不像对象”，没有把 suite 中声明的工具参数要求和实际 `ToolSpec.parameters` 对齐。

这会导致一个严重的 harness 层问题：评测套件本身可能要求模型调用不存在的参数字段，或者要求一个数值参数满足字符串谓词，但系统不会在运行模型前发现。对于面向 9B/flash 小模型的 harness，这类错误会污染失败样本，让我们误判模型能力、repair 能力和工具治理能力。

## 已完成变更

1. `validate_eval_suite` 新增 `tool_schemas` 上下文。
   - 保持 `available_tools` 向后兼容。
   - 如果只传入 `tool_schemas`，验证器会自动使用 schema key 作为可用工具集合。
   - CLI 和 generic suite runner 可以继续通过 `**generic_eval_validation_context(...)` 调用。

2. `generic_eval_validation_context` 现在导出真实内置工具 schema。
   - `available_tools`
   - `available_quality_gates`
   - `tool_schemas`

3. `required_tool_arguments` 增加 schema-aware 静态校验。
   - 工具不存在：继续报 `unknown_tool`。
   - 参数字段不存在：报 `unknown_tool_argument`。
   - 字面值不匹配工具参数 schema：报 `tool_argument_schema_mismatch`。
   - 文本谓词用于纯数值/布尔参数：报 `tool_argument_predicate_type_mismatch`。
   - `in` 谓词候选值逐项按参数 schema 校验。
   - `equals` 谓词按参数 schema 校验。
   - `contains`、`startswith`、`endswith` 要求谓词值本身是字符串，并要求目标参数 schema 至少兼容 string/array/object。

4. 保留 partial expectation 语义。
   - `required_tool_arguments` 本质上是“期望模型调用时包含这些参数约束”，不是完整工具调用参数。
   - 因此验证器不会用工具 schema 的 `required` 字段强制 suite 中写全所有参数。
   - 对嵌套对象只在有 schema properties 时递归检查已声明字段。

## 新增测试覆盖

新增/扩展测试覆盖了以下情况：

1. 合法参数谓词通过校验。
2. suite 要求不存在的工具参数字段时失败。
3. suite 给整数参数配置字符串字面值时失败。
4. suite 给整数参数配置 `contains` 文本谓词时失败。
5. suite 给整数参数配置 `in: [30, "fast"]` 时逐项发现 `"fast"` 类型错误。
6. generic eval validation context 确认可导出 `read_file.path` 和 `run_command.timeout` 的真实 schema。

## 对 Metis Harness 的意义

这一步不是场景能力，而是 harness 底座能力。它把 eval suite 从“松散 JSON 配置”推进到“和工具 registry 绑定的可验证契约”。

对后续不同场景智能体开发的直接价值：

1. 新场景注册新工具后，可以在跑模型前发现 eval suite 是否引用了不存在的工具参数。
2. 小模型失败样本更干净，能区分“模型没有按要求调用工具”和“评测配置本身错误”。
3. repair 指标更可信，避免把 suite 设计错误误算成模型 schema repair 失败。
4. 工具 schema、评测任务、质量门和 CLI 运行入口开始形成闭环。

## 仍然存在的问题

1. 目前只校验 JSON Schema 的小子集，仍缺少 `additionalProperties`、`minimum`、`maximum`、`pattern`、`minItems` 等约束。
2. 对 `oneOf` 的递归对象校验还比较保守，只取第一个可发现 properties 的分支。
3. `contains` 对 array/object 的语义仍依赖 EvalRunner 的字符串化匹配，后续应该增加显式 predicate 类型，例如 `contains_item`、`has_key`、`matches_regex`。
4. suite validation 报告还没有输出 inventory 摘要，使用者需要另跑 `eval list-tools` 才能知道合法参数。
5. 还没有把 schema-aware validation 加入持续 gate 的文档化 release profile。

## 验证结果

- `python -m pytest tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`
  - 结果：20 passed
- `python -m pytest tests\unit\test_cli_eval.py -q`
  - 结果：36 passed
- `python -m compileall -q metis`
  - 结果：通过

