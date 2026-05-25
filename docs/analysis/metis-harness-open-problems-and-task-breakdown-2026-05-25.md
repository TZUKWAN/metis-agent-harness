# Metis Harness 当前问题分析与任务清单

日期：2026-05-25

## 最新进展：Iteration 124

本轮把 requirements verifier 从简单字符串覆盖升级到结构化 requirement criteria。第123轮已经让 `requirements` 成为 `EvalTaskSpec` 一等字段，并让 runner 把 requirements 传给 `requirements_covered` gate；但 gate 仍主要靠 substring 匹配。对生产级 harness 来说，acceptance criteria 需要能声明 id、证据类型、证据引用和最低证据强度，否则“提到了关键词”就可能被误判为覆盖。

已完成：

1. `EvalTaskSpec` 新增：
   - `requirement_criteria: list[dict]`
2. `EvalRunner._quality_gate_results()` 现在传入：
   - `requirement_criteria`
3. `suite_validation` 现在识别：
   - `requirement_criteria`
   - 并验证它是 object list。
4. `suite-schema-v1.json` 新增：
   - `requirement_criteria`
5. `suite-schema.md` 新增字段说明：
   - 可包含 `id`
   - `text`
   - `required_source_type`
   - `required_source_ref`
   - `min_strength`
6. `requirements_covered_gate()` 现在支持两类输入：
   - legacy string `requirements`
   - structured `requirement_criteria`
7. structured criteria 支持：
   - requirement id；
   - criterion text；
   - required evidence source type；
   - required evidence source ref；
   - minimum evidence strength。
8. gate metadata 现在输出：
   - `requirement_criteria`
   - `missing_requirement_ids`
9. strength 检查支持：
   - `weak < medium < strong`
10. targeted eval generation 现在从 quality gate metadata 中保留：
    - `requirement_criteria`
11. 新增测试覆盖：
    - weak evidence 不满足 `min_strength=strong`；
    - missing requirement id 被记录；
    - runner 将 `requirement_criteria` 传给 gate；
    - compare/stub/materialized suite 保留 structured criteria；
    - docs schema snapshot 与 dataclass 字段同步。

对 harness 的意义：

1. requirements coverage 不再只是“输出里包含某个词”，而是可以绑定证据来源和证据强度。
2. 9B 模型可以继续负责生成内容，但 verifier 判断是否达标时有更强的客观依据。
3. 需求缺口能被定位到 stable requirement id，后续 dashboard、repair task、趋势分析都能按 id 聚合。
4. 这让 Metis 从“自然语言要求 + gate”走向“结构化验收标准 + evidence verifier”。

验证：

- `python -m pytest tests\unit\test_quality_gates.py tests\unit\test_eval_runner.py tests\unit\test_eval_compare.py tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py -q`：`117 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. `requirement_criteria` 应进一步支持 `required_artifact_path` 和 `required_tool`。
2. requirement ids 可以进入 compare 的 drift summary，形成 requirement-gap trend。
3. `no_fake_completion` 的 claim/evidence metadata 仍需标准化。
4. release gate 需要支持 required gate presence。
5. attestation 仍未签名。

## 最新进展：Iteration 123

本轮把 requirements 从 prompt 上下文升级为 `EvalTaskSpec` 的一等字段，并让 runtime quality gate 直接消费。第122轮已经把 `missing_requirements` 显式带入 targeted eval prompt 和 suite wrapper，但 `requirements_covered` gate 在执行时仍只能从 quality context 读取 `requirements`，而 runner 没有把 task spec 中的 acceptance criteria 传进去。也就是说，需求覆盖还没有真正进入可执行 eval contract。

已完成：

1. `EvalTaskSpec` 新增：
   - `requirements: list[str]`
2. `EvalRunner._quality_gate_results()` 现在给 quality gate context 传入：
   - `requirements: task.requirements`
3. `suite_validation.LIST_FIELDS` 新增：
   - `requirements`
4. `suite-schema-v1.json` 的 `eval_task_spec.properties` 新增：
   - `requirements`
5. `suite-schema.md` 新增字段说明：
   - requirements 是 quality gates 可验证的 acceptance criteria。
6. `build_eval_stubs_from_repair_tasks()` 现在从 quality gate metadata 派生：
   - `requirements`
7. 对 `requirements_covered` gate drift：
   - metadata 中的 `requirements` 会进入 `eval_task_spec.requirements`；
   - `missing_requirements` 作为补充也会并入 requirements；
   - 去重后保留稳定顺序。
8. 新增 runner 测试确认：
   - `EvalTaskSpec(requirements=[...], quality_gates=["requirements_covered"])`
   - runtime gate 能读到 requirements；
   - 缺失项进入 gate metadata；
   - `quality_failures == 1`。
9. 新增 compare/stub 测试确认：
   - `requirements_covered` drift 会生成 `task_spec.requirements`；
   - materialized suite 保留该字段。

对 harness 的意义：

1. acceptance criteria 不再只是 prompt 内容，而是 eval contract 的结构化字段。
2. 9B 模型可以被更强的 harness 约束：模型负责产出，runner/gate 负责验证需求是否覆盖。
3. 这让 requirements coverage 形成闭环：
   - gate 输出 missing requirements；
   - compare 识别 gate drift；
   - repair task 保留缺口；
   - targeted eval 写入 requirements；
   - runtime gate 再次验证 requirements。
4. 这比自然语言 prompt 更接近生产级 harness：需求、证据、artifact、gate 都是机器可读契约。

验证：

- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_eval_runner.py tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py -q`：`111 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. `requirements_covered` 目前是简单 substring coverage，后续应支持 requirement ids、source tiers、exact evidence refs。
2. `no_fake_completion` 的 claim/evidence metadata 仍需标准化。
3. release gate 需要支持 required gate presence。
4. dashboard 需要 requirement-gap trend。
5. attestation 仍未签名。

## 最新进展：Iteration 122

本轮把 `requirements_covered` 的 `missing_requirements` 编译进 targeted eval stub 和 materialized suite。第121轮已经让默认 gate 输出结构化 `missing_requirements`，但这些字段还只是藏在 `quality_gate_changes.current_metadata` 里。对 9B 模型来说，修复任务必须显式告诉它哪些 acceptance criteria 没覆盖，而不是让它从 JSON metadata 或自然语言 message 中猜。

已完成：

1. `_quality_gate_missing_requirements()` 新增：
   - 从 `current_metadata.missing_requirement` 读取单个缺失需求；
   - 从 `current_metadata.missing_requirements` 读取缺失需求列表；
   - fallback 到 baseline metadata。
2. generated targeted eval stub 现在保留：
   - `missing_requirements`
3. materialized targeted suite wrapper 现在保留：
   - `missing_requirements`
4. `eval_stubs_to_markdown()` 展示：
   - `Missing requirements`
5. `eval_suite_to_markdown()` 展示：
   - `Missing requirements`
6. `_eval_stub_prompt()` 新增 requirement coverage context：
   - 明确列出 previously missing requirements；
   - 要求 final output 或 recorded evidence 让每个 requirement 可验证。
7. `suite-schema-v1.json` wrapped task metadata 新增：
   - `missing_requirements`
8. `suite-schema.md` 同步说明该字段。
9. 新增单测覆盖：
   - `requirements_covered` gate drift；
   - `missing_requirements=["citations", "risk register"]`；
   - stub prompt 包含缺失需求；
   - Markdown 和 materialized suite 保留缺失需求。

对 harness 的意义：

1. 需求覆盖失败现在从“gate message”变成“targeted eval contract”。
2. 9B 模型不需要推断 acceptance criteria；harness 将缺口显式写入任务上下文。
3. downstream CI/dashboard 可以直接读取 `missing_requirements`，不用解析 gate metadata。
4. 这让 Metis 更接近“需求驱动 verifier”，而不是单纯行为回归测试器。

验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：`51 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. `missing_requirements` 还可以进一步变成 dedicated `requirements` field，供 `requirements_covered` gate 在 targeted eval runtime 中直接使用。
2. `no_fake_completion` 的 claim/evidence metadata 仍需标准化。
3. release gate 需要支持 required gate presence。
4. dashboard 需要 gate-level trend 和 requirement-gap trend。
5. attestation 仍未签名。

## 最新进展：Iteration 121

本轮把默认 quality gates 的失败输出标准化为可机器消费的 metadata。第120轮已经能把 `quality_gate_changes.current_metadata` 编译成 targeted eval 的 `expected_artifacts` 和 `required_evidence_sources`，但默认 gate 自身仍主要返回人类可读 message。也就是说，如果 gate 不主动输出结构化 metadata，compare/diagnosis/stub 只能得到弱证据。

已完成：

1. `artifact_exists` 现在输出：
   - `expected_artifacts`
   - `missing_artifacts`
   - `artifact_count`
2. `artifact_non_empty` 现在输出：
   - `expected_artifacts`
   - `empty_artifacts`
   - `artifact_count`
3. `no_placeholder` 现在输出：
   - `expected_artifacts`
   - `placeholder_artifacts`
   - `placeholder_message`
   - `artifact_count`
4. `requirements_covered` 现在输出：
   - `requirements`
   - `missing_requirements`
   - `evidence_count`
   - `artifact_count`
5. 成功路径也会输出基础 metadata：
   - artifact gates 输出已检查 artifact 列表和数量；
   - requirements gate 输出 requirements、missing_requirements 空列表和计数。
6. 新增单测覆盖：
   - no artifact；
   - empty artifact；
   - placeholder artifact；
   - missing requirement。

对 harness 的意义：

1. gate failure 不再只有字符串，后续 compare、diagnosis、repair task、targeted eval 可以消费稳定字段。
2. 第120轮的 metadata-to-constraint 编译现在有了默认 gate 的上游数据来源。
3. 小模型收到的修复任务会更像结构化 contract，而不是自然语言报错。
4. 这提升了 “9B 模型 + 强 harness” 的真实上限：模型少猜一点，harness 多验证一点。

验证：

- `python -m pytest tests\unit\test_quality_gates.py -q`：`5 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. `requirements_covered` 的 `missing_requirements` 还没有进一步映射到 targeted eval prompt constraints 或 evidence requirements。
2. `no_fake_completion` 的 metadata 可以继续标准化 claim/evidence 映射。
3. release gate 需要支持 required gate presence。
4. dashboard 需要 gate-level trend。
5. attestation 仍未签名。

## 最新进展：Iteration 120

本轮把 `quality_gate_changes` 进一步映射成 targeted eval 的硬约束。第119轮已经让 gate name、failure message、metadata 进入 stub prompt、stub JSON 和 materialized suite，但这些信息仍主要是上下文；如果 gate metadata 里已经声明了 artifact path 或 evidence source，targeted eval 应该直接生成可执行的 `expected_artifacts` 和 `required_evidence_sources`，而不是让 9B 模型自己从 prompt 里推理。

已完成：

1. `_eval_stub_for_repair_task()` 现在从 `quality_gate_changes` 派生：
   - `expected_artifacts`
   - `required_evidence_sources`
2. artifact 类 quality gate 会映射 artifact metadata：
   - `artifact_exists`
   - `artifact_non_empty`
   - `no_placeholder`
3. 支持从 metadata 中读取 artifact 路径字段：
   - `path`
   - `paths`
   - `artifact_path`
   - `artifact_paths`
   - `expected_artifact`
   - `expected_artifacts`
4. 支持从 metadata 中读取 evidence source 字段：
   - `source_type`
   - `source_types`
   - `evidence_source`
   - `evidence_sources`
   - `required_evidence_source`
   - `required_evidence_sources`
5. generated `eval_task_spec` 现在在有对应 metadata 时写入：
   - `expected_artifacts`
   - `required_evidence_sources`
6. 新增测试确认：
   - `artifact_exists` gate drift 的 `path=outputs/report.md` 会进入 `expected_artifacts`；
   - `required_evidence_sources=["tool_output"]` 会进入 eval task spec；
   - materialized suite 保留这些硬约束。

对 harness 的意义：

1. gate drift 不再只是“告诉模型哪里坏了”，而是直接变成 runner 能执行的 artifact/evidence 约束。
2. 小模型不需要自行推断“缺 artifact”应该对应哪个 `expected_artifacts` 字段，harness 会把结构化 metadata 编译成 eval contract。
3. 这让 targeted eval 更像 deterministic verifier，而不是单纯 prompt-based reproduction。
4. 对 9B 模型尤其重要：越多质量标准由 harness 直接约束，模型越少承担隐式协议理解负担。

验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：`50 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 默认 quality gates 自身还应在失败时输出更标准的 metadata，例如 artifact path list、missing artifacts、empty artifacts。
2. `requirements_covered` gate 可以把 missing requirements 编译成 required evidence 或 prompt constraints。
3. release gate 仍需支持 required gate presence。
4. dashboard 仍需 gate-level trend。
5. attestation 仍未签名。

## 最新进展：Iteration 119

本轮把 `quality_gate_failed` 从“compare/diagnosis 能发现的问题”推进到“targeted eval stub 能携带并复现的问题”。第118轮已经让 `eval compare` 识别质量门漂移，并把 `quality_gate_changes` 写入 diagnosis 与 repair task；但 `build_eval_stubs_from_repair_tasks()` 仍没有把 gate name、gate metadata、失败消息带入 stub prompt、stub JSON、materialized suite wrapper。这会让后续自动修复链路丢掉最关键的失败上下文。

已完成：

1. `_eval_stub_for_repair_task()` 现在读取：
   - `quality_gate_changes`
   - `quality_gate_names`
2. generated stub 现在保留：
   - `quality_gate_changes`
   - `quality_gate_names`
3. generated `eval_task_spec` 现在在有 gate drift 时写入：
   - `quality_gates`
4. `_eval_stub_prompt()` 现在注入 quality gate drift context：
   - failed gate 列表；
   - task id；
   - gate name；
   - baseline/current pass state；
   - gate failure message；
   - gate metadata。
5. `suggested_assertion` 对 `quality_gate_failed` 现在变成 gate-aware assertion：
   - 同一批 gate 输入、metadata、artifact expectation 必须从 fail 变 pass。
6. `eval_stubs_to_markdown()` 展示：
   - `Quality gate changes`
7. `materialize_eval_suite_from_stubs()` 保留：
   - `quality_gate_changes`
8. `eval_suite_to_markdown()` 展示：
   - `Quality gate changes`
9. `suite-schema-v1.json` 的 wrapped task metadata 增加：
   - `run_metadata`
   - `stub_type`
   - `trust_state`
   - `target_runs`
   - `quality_gate_changes`
   - `quality_gate_names`
10. `suite-schema.md` 同步说明 quality gate drift wrapper metadata。
11. 新增单测覆盖：
    - `quality_gate_failed` repair task；
    - gate name 进入 stub；
    - gate metadata 进入 prompt；
    - `quality_gates` 进入 eval task spec；
    - materialized suite 保留 gate drift payload；
    - Markdown 可读展示 gate change。

对 harness 的意义：

1. 自动修复链路不再只知道“质量门失败”，而是知道“哪个 task 的哪个 gate 因为什么 metadata 失败”。
2. 对 9B 模型很关键：小模型不适合从长错误文本里推理 gate 语义，harness 必须把失败形状压缩成结构化、可执行、可验证的输入。
3. targeted eval stub 现在可以直接要求同名 gate 在修复后 pass，让回归验证从“模糊复现问题”变成“复现 gate 输入并通过 gate”。
4. materialized suite 保存 gate drift payload，后续 CI、dashboard、repair loop 可以在不回读 diagnosis 的情况下理解这个 targeted eval 的来源。

验证：

- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_docs_exist.py -q`：`53 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. targeted eval stub 还没有把 `quality_gate_changes` 映射成更具体的 expected artifact / required evidence fields。
2. `QualityGateRunner` 仍需标准化 gate metadata schema。
3. release gate 需要支持“某个 gate 必须存在并运行”，避免 gate 漏跑。
4. dashboard 可以基于 `quality_gate_names` 做 gate-level trend。
5. attestation 仍未签名。

## 最新进展：Iteration 118

本轮把 `eval compare` 接入 `quality_gate_results` 漂移检测。第116轮和第117轮已经让 deterministic artifact fixture 与普通 model behavior eval 都能把质量门结果写入 `EvalResult`、报告、失败 artifact 和 timeline，但跨 run 比较仍然没有消费这些结构化结果。这样会出现一种危险情况：任务 `success=True`、核心数值指标也没有退化，但某个关键交付质量门从 pass 变成 fail，release compare 仍然可能看不出交付质量已经退化。

已完成：

1. `compare_eval_runs()` 现在计算 `quality_gate_diff`：
   - `new_failed_gates`
   - `resolved_failed_gates`
2. `new_failed_gates` 的结构化字段包括：
   - `task_id`
   - `gate`
   - `baseline_passed`
   - `current_passed`
   - `current_message`
   - `current_metadata`
3. release/strict profile 现在会把新增失败质量门标记为 regression reason：
   - `quality_gate_failed`
4. `regression_reason_links` 现在为 `quality_gate_failed` 连接：
   - task ids；
   - failure artifacts；
   - failure timelines；
   - `quality_gate_changes`。
5. comparison Markdown 新增 `## Quality Gate Drift`：
   - 展示新失败 gate；
   - 展示已恢复 gate。
6. regression reason link Markdown 现在展示：
   - `changes=a.markdown_report` 这种可扫描格式。
7. diagnosis 现在保留：
   - `quality_gate_changes`
8. diagnosis Markdown 现在展示：
   - `Quality gate changes`
9. repair task 现在保留：
   - `quality_gate_changes`
10. `quality_gate_failed` 的 repair owner area 现在是：
    - `quality-gates-and-evidence`
11. `quality_gate_failed` 的 suggested eval 现在明确要求：
    - 构造 deterministic eval；
    - 复现质量门输入；
    - 要求该 gate pass。
12. likely source modules 现在能根据质量门失败归因到：
    - `metis/quality/gates.py`
    - `metis/quality/runner.py`
    - `metis/evals/runner.py`
    - `metis/evals/compare.py`
    - `metis/evidence/ledger.py`
13. 新增单测覆盖“任务成功但质量门漂移失败”的场景：
    - baseline `markdown_report` gate pass；
    - current `markdown_report` gate fail；
    - success rate 保持 100%；
    - compare 仍然必须判定 regression。

对 harness 的意义：

1. Metis 不再只用 success rate 和错误计数判断交付质量。质量门本身成为 release compare 的一等证据。
2. 小模型常见问题不是“完全失败”，而是“看起来完成了，但报告、证据、artifact、引用、格式或可信度不达标”。本轮让这种静默质量退化进入自动阻断链路。
3. repair task 现在能直接拿到 gate name 和 gate metadata，不需要从自然语言错误里猜测问题来源。
4. 对 9B/flash 模型尤其关键：模型越弱，越需要 harness 把失败边界结构化、显式化、可路由化，而不是让模型自己推理隐含质量标准。

验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：`49 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. `QualityGateRunner` 仍需定义标准化 metadata schema，避免不同 gate 的 metadata 字段长期漂移。
2. `quality_gate_failed` 生成 targeted eval stub 时，可以进一步把 gate name、metadata、expected artifact path 写入 eval prompt 或 deterministic fixture。
3. dashboard 可以增加 gate-level trend view，按 gate name 追踪 pass/fail 漂移。
4. release gate 可以进一步支持“指定质量门必须存在”，避免某次运行因为漏跑 gate 而被误判为没有失败。
5. attestation 仍未签名，后续需要接入签名策略。

## 最新进展：Iteration 117

本轮把普通 model behavior eval 的 quality gate result 也结构化写入结果、失败 artifact 和 timeline。第116轮先解决了 deterministic artifact fixture，但普通模型任务仍然只把 gate 失败计入 `quality_failures`，没有保留具体 gate name/message/metadata。这会让 dashboard、diagnosis、repair agent 在模型行为 eval 中仍然缺少直接证据。

已完成：

1. `EvalRunner.run_task()` 对普通模型任务现在执行：
   - `_quality_gate_results()`
   - `_quality_failure_count()`
2. `quality_failures` 继续保持兼容语义：
   - expected artifact 缺失；
   - required evidence source 缺失；
   - failed quality gate 数量。
3. `EvalResult.quality_gate_results` 现在覆盖：
   - deterministic fixture；
   - 普通模型行为 eval。
4. `eval-report.json` 中每个 result 都包含 `quality_gate_results`。
5. `eval-report.md` 的 `## Quality Gate Results` 同时展示模型行为任务和 deterministic fixture 的 gate 结果。
6. failure artifact JSON 新增：
   - `quality_gate_results`
7. failure timeline JSON 新增事件：
   - `event_type: quality.gate`
   - `gate_name`
   - `status`
   - `message`
   - `metadata`
8. failure timeline Markdown 展示 quality gate 事件。
9. 单测覆盖：
   - 普通模型行为任务遇到未知 gate `markdown_report` 时，report JSON、report Markdown、failure artifact、timeline JSON、timeline Markdown 都包含结构化 gate failure。

对 harness 的意义：

1. 所有 eval 类型的 gate 结果现在都能被机器读取，不再只靠失败数量。
2. 小模型后续诊断时可以直接看到“哪个 gate 阻断了任务”，而不是从自然语言错误中猜。
3. 这把 quality gate 从“统计指标”提升成“traceable evidence event”。
4. 后续 comparison 可以基于 gate result drift 做更细粒度回归判断。

验证：

- `python -m pytest tests\unit\test_eval_runner.py -q`：`40 passed`

新的任务缺口：

1. `comparison` 还没有比较 `quality_gate_results` drift。
2. repair task 可以按 gate name 生成更精确的 owner area 和 likely source modules。
3. `QualityGateRunner` 可输出更标准化的 gate metadata schema。
4. attestation 仍未签名，需要接入签名策略。

## 最新进展：Iteration 116

本轮把 deterministic fixture 的 quality gate result metadata 写入 `EvalResult` 和 eval report。第115轮已经让 artifact verification fixture 可以绕过 provider 并执行 `verify_run_attestation()`，但输出主要靠 `errors` 和 `quality_failures`，缺少结构化 gate 结果。dashboard、repair agent、CI 如果想知道哪个 gate 失败、失败消息是什么、metadata 里有哪些 target run，就必须解析文本。

已完成：

1. `EvalResult` 新增：
   - `quality_gate_results`
2. 每个 gate result 记录：
   - `name`
   - `passed`
   - `message`
   - `metadata`
3. artifact verification fixture 现在通过 `QualityGateRunner` 执行：
   - 默认 gate：`run_attestation_verifies`
   - 或使用 task spec 中声明的 `quality_gates`
4. 成功 fixture 的 result 会写入：
   - `quality_gate_results[0].name == "run_attestation_verifies"`
   - `passed == True`
   - metadata 中包含 `target_run_dirs`
5. 失败 fixture 的 result 会写入：
   - `passed == False`
   - message 中包含 side-specific attestation failure；
   - errors 仍保留失败 message，兼容原有失败链路。
6. `eval-report.json` 自动包含 `quality_gate_results`。
7. `eval-report.md` 新增：
   - `## Quality Gate Results`
8. 没有 gate result 的任务显示 `- None`，避免报告结构缺失。

对 harness 的意义：

1. deterministic verifier 的结果变成机器可读，不再只是 error 字符串。
2. dashboard 可以直接展示 gate name、pass/fail、metadata。
3. repair agent 可以用 gate metadata 找到 target run，而不是从自然语言里猜。
4. 对 9B 模型尤其重要：小模型拿到的 repair payload 越结构化，越少把 artifact 问题误修成行为问题。

验证：

- `python -m pytest tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_quality_gates.py -q`：`61 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 普通 model behavior eval 的 quality gate result 也应写入 `quality_gate_results`，目前主要补的是 deterministic fixture。
2. failure artifacts/timelines 应包含 `quality_gate_results`，方便 trace review。
3. `comparison` 可以比较 gate result drift。
4. attestation 仍未签名，需要接入签名策略。

## 最新进展：Iteration 115

本轮让 generic suite runner 真正执行 `requires_model_execution=False` 的 artifact verification fixture，而不是只在 stub/materialized suite 中保留 metadata。第114轮已经生成了 artifact verification stub，但 runner 仍缺少确定性执行分支，CLI 也会在没有 provider 环境变量时拒绝任何 generic suite。这会导致 artifact verification fixture 仍然不能作为独立 harness verifier 运行。

已完成：

1. `EvalTaskSpec` 新增字段：
   - `fixture_type`
   - `requires_model_execution`
   - `artifact_verification`
2. `eval_task_specs_from_suite_payload()` 现在会为 artifact verification fixture 注入 `target_run_dirs`：
   - 从 suite 顶层 `baseline.run_dir` / `current.run_dir` 读取；
   - 根据 task spec 中的 `artifact_verification.target_runs` 映射。
3. `EvalRunner.run_task()` 新增 deterministic fixture 分支：
   - 当 `requires_model_execution=False` 时，不调用 `AgentLoop`；
   - `fixture_type=artifact_verification` 时，对每个 `target_run_dirs` 执行 `verify_run_attestation()`；
   - 成功返回 `status=verified`、`turns_used=0`、`tool_calls=0`；
   - 失败返回 `status=failed`，errors 中包含 side-specific attestation failures。
4. 新增 quality gate：
   - `run_attestation_verifies`
5. `generic_eval_validation_context()` 和 `generic_eval_quality_gate_inventory()` 现在暴露该 gate。
6. `generic_eval_suite_requires_model_execution(suite_path)` 新增：
   - 全 deterministic fixture suite 返回 `False`；
   - 混合 suite 或普通 suite 返回 `True`。
7. CLI `metis eval run-suite` 现在只在 suite 需要模型执行时要求：
   - `METIS_BASE_URL`
   - `METIS_API_KEY`
   - `METIS_MODEL`
8. 全 artifact fixture suite 可以在无 provider 环境变量时运行，不伪造模型结果。
9. suite schema snapshot 和文档新增：
   - `fixture_type`
   - `requires_model_execution`
   - `artifact_verification`
   - artifact verification fixture 说明。

对 harness 的意义：

1. Metis 的 eval suite 现在不只是一组模型调用，也可以包含 deterministic harness verification。
2. artifact 可信修复可以独立运行，不消耗 provider token，不依赖 9B 模型。
3. 9B 模型不会被要求处理本该由 verifier 处理的 digest/size/missing-subject 问题。
4. 这把 targeted repair loop 分成两条明确路径：
   - 模型行为回归：调用 provider；
   - harness artifact verification：确定性本地验证。

验证：

- `python -m pytest tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_cli_eval.py tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py tests\unit\test_quality_gates.py -q`：`118 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. `run_attestation_verifies` quality gate 目前主要用于 inventory 和 fixture 语义，后续可让 `_quality_failures()` 在 deterministic fixture context 中也记录 gate result metadata。
2. `eval-report.md` 对 deterministic fixture 的 status/turns/tools 展示还可以更明确地区分 verifier task。
3. materialized suite schema 可进一步约束 `artifact_verification.target_runs` 只能为 `baseline/current`。
4. attestation 仍未签名，需要接入签名策略。

## 最新进展：Iteration 114

本轮让 `attestation_untrusted` 生成 artifact verification fixture，而不是普通模型行为 targeted eval。第113轮已经把 artifact trust repair 放到 repair plan phase-0，但后续 `build_eval_stubs_from_repair_tasks()` 仍然会把所有 repair task 转成同一种模型行为 eval stub。这样会把“run bundle 不可信”错误转换成“让模型复现/修复某个行为失败”，方向不对。

已完成：

1. `_eval_stub_for_repair_task()` 对 artifact integrity task 新增专用分支。
2. artifact integrity task 判定复用：
   - `reason == "attestation_untrusted"`；
   - 或 `owner_area == "artifact-integrity-and-provenance"`；
   - 或 task 带有 `trust_state`。
3. 新增 artifact verification stub：
   - `stub_type: artifact_verification`
   - id 前缀：`artifact-verification-...`
   - 保留 `trust_state`
   - 计算 `target_runs`
   - 保留 source repair task、priority、owner area、likely source modules
4. artifact verification `eval_task_spec`：
   - `fixture_type: artifact_verification`
   - `requires_model_execution: False`
   - `allowed_tools: []`
   - `max_turns: 1`
   - `quality_gates: ["run_attestation_verifies"]`
   - 记录 required checks：
     - `run-attestation.json exists`
     - all subjects exist
     - subject sha256 matches local bytes
     - subject sizes match local bytes
     - manifest/eval-report/task-specs are covered
5. artifact verification prompt 明确：
   - 不验证模型行为；
   - 只验证 run attestation 通过。
6. `eval_stubs_to_markdown()` 展示：
   - stub type
   - target runs
   - trust state
7. `materialize_eval_suite_from_stubs()` 保留：
   - `stub_type`
   - `trust_state`
   - `target_runs`
8. 单测覆盖：
   - `attestation_untrusted` 生成 artifact verification stub；
   - target run 根据 trust_state 选择 current；
   - task spec 不需要 model execution；
   - allowed tools 为空；
   - materialized suite 保留 trust metadata。

对 harness 的意义：

1. artifact 可信问题不再被误包装成模型行为回归。
2. 9B 小模型在自动修复链路中不会被要求“复现一个 digest mismatch”，而是拿到明确的 artifact verification fixture。
3. targeted eval 体系开始区分两类 regression material：
   - model behavior eval；
   - harness artifact verification fixture。
4. 这更符合真实 harness 底座定位：不是所有修复都要让模型跑一遍，有些修复应该由确定性 verifier 完成。

验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：`48 passed`

新的任务缺口：

1. generic suite runner 需要识别 `requires_model_execution=False` 的 fixture，并用 deterministic verifier 执行，而不是调用 provider。
2. suite schema 文档需要定义 `fixture_type`、`requires_model_execution` 和 `artifact_verification`。
3. `run_attestation_verifies` quality gate 需要进入 quality gate inventory。
4. attestation 仍未签名，需要接入签名策略。

## 最新进展：Iteration 113

本轮把 artifact integrity repair 提升为 repair plan 的前置阶段。第112轮已经让 `attestation_untrusted` 进入 repair task，并归类到 `artifact-integrity-and-provenance`，但 repair plan 的阶段仍然从“stop release blockers”开始。由于不可信 artifact 会污染后续所有质量解释，它应该在模型行为修复、targeted eval、owner area 稳定化之前先被处理。

已完成：

1. `build_repair_plan()` 新增动态前置阶段：
   - `phase-0-restore-artifact-trust`
2. 只有存在 artifact integrity task 时才插入该阶段，legacy/普通行为回归计划不受影响。
3. artifact integrity task 判定条件：
   - `reason == "attestation_untrusted"`；
   - 或 `owner_area == "artifact-integrity-and-provenance"`；
   - 或 task 带有 `trust_state`。
4. `phase-0-restore-artifact-trust` 描述：
   - 先 repair/regenerate untrusted run bundles；
   - 再解释 model behavior、metrics、regression deltas。
5. artifact integrity task 仍会同时进入 release blocker phase，因为它也是 critical release blocker。
6. repair plan markdown 自动展示该前置阶段。
7. 单测覆盖：
   - 有 artifact integrity task 时第一个 phase 是 `phase-0-restore-artifact-trust`；
   - 该 phase 只包含 artifact trust task；
   - release blocker phase 仍包含所有 critical/high task；
   - owner area 排序优先显示 `artifact-integrity-and-provenance`。

对 harness 的意义：

1. 自动修复顺序更符合生产事实：先证明 run bundle 可信，再解释模型/工具/轨迹问题。
2. 避免 9B 小模型把 artifact 损坏误修成 prompt、schema、tool policy 或 runtime loop 问题。
3. repair plan 从“任务列表”进一步变成“可执行的因果顺序计划”。

验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：`47 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. targeted eval stub 不应该为 `attestation_untrusted` 生成模型行为 eval，而应该生成 artifact verification fixture。
2. repair plan next actions 可以优先点名 phase-0。
3. `gate.md` 和 `comparison.md` 仍可继续增加 subject 统计和失败 subject 明细。
4. attestation 仍未签名，需要接入签名策略。

## 最新进展：Iteration 112

本轮把 comparison trust 状态继续传入 diagnosis 和 repair task。第111轮已经在 comparison 顶层输出 `baseline_untrusted/current_untrusted`，但自动修复链路拿到的是 `diagnosis.json` 和 `repair-tasks.json`，如果 trust 状态只停留在 comparison 层，repair agent 仍需要回读整份 comparison 才知道应该修 artifact 可信链路，而不是修模型行为。

已完成：

1. `eval_run_comparison_diagnosis()` 现在继承：
   - `baseline_untrusted`
   - `current_untrusted`
2. `attestation_untrusted` diagnosis entry 新增：
   - `trust_state`
3. `trust_state` 包含：
   - `baseline_untrusted`
   - `current_untrusted`
   - `baseline_failures`
   - `current_failures`
4. `eval_run_diagnosis_to_markdown()` 现在展示：
   - diagnosis 顶层 baseline/current untrusted；
   - 每个 entry 的 trust state。
5. `build_repair_tasks_from_diagnosis()` 现在把 `trust_state` 原样写入 repair task。
6. `attestation_untrusted` repair task 现在被分类为：
   - priority: `critical`
   - owner_area: `artifact-integrity-and-provenance`
7. `attestation_untrusted` 的 likely source modules 现在指向：
   - `metis/evals/attestation.py`
   - `metis/evals/compare.py`
   - `metis/evals/gate.py`
   - `metis/evals/runner.py`
8. suggested eval 明确要求：
   - 先 regenerate/repair untrusted run artifact bundle；
   - 重新跑 attestation verification；
   - 再重复 comparison。

对 harness 的意义：

1. repair agent 不需要解析 comparison 原文，也不需要重新推理 trust failure 来源。
2. artifact 可信问题从“比较层诊断”推进成“可执行 repair task”。
3. 这让 Metis 对 9B 模型更友好：小模型拿到的任务是结构化、归因明确、修复边界清楚的，而不是一堆混在质量回归里的文本提示。
4. 自动闭环现在能区分：
   - artifact bundle 不可信；
   - pre-run/post-run contract 不一致；
   - task spec drift；
   - 模型行为指标退化；
   - schema repair hint 退化。

验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：`46 passed`

新的任务缺口：

1. repair plan 的 owner area 汇总需要针对 `artifact-integrity-and-provenance` 给出专门 phase。
2. targeted eval stub 不应该为 `attestation_untrusted` 生成模型行为 eval，而应该生成 artifact verification fixture。
3. `gate.md` 和 `comparison.md` 仍可继续增加 subject 统计和失败 subject 明细。
4. attestation 仍未签名，需要接入签名策略。

## 最新进展：Iteration 111

本轮在第110轮基础上补齐 comparison 顶层 trust 标志。第110轮已经把 attestation failures 写入 `attestation_diff`，并在 release/strict profile 下生成 `attestation_untrusted`。但 CI、dashboard、repair agent 如果只想快速判断哪一侧 run bundle 不可信，仍需要解析 failure list。本轮把这个判断提升为直接字段。

已完成：

1. `compare_eval_runs()` 顶层新增：
   - `baseline_untrusted`
   - `current_untrusted`
2. 字段语义：
   - `baseline_untrusted=True` 表示 baseline run 的 attestation 缺失、损坏或与本地 artifact bytes 不一致；
   - `current_untrusted=True` 表示 current run 的 attestation 缺失、损坏或与本地 artifact bytes 不一致；
   - 双方 legacy run 都没有 attestation 时保持兼容，不自动置为 untrusted。
3. comparison Markdown 的 `## Artifact Attestation` 新增：
   - baseline untrusted；
   - current untrusted。
4. 单测覆盖：
   - current report 被篡改时 `current_untrusted=True`；
   - current attestation 单侧缺失时 `current_untrusted=True`；
   - baseline attestation 正常时 `baseline_untrusted=False`。

对 harness 的意义：

1. 外部 CI 不用解析自然语言 failure 字符串就能阻断不可信比较。
2. repair agent 可以直接按 `baseline_untrusted/current_untrusted` 决定修复入口：是修 baseline artifact，还是修 current artifact。
3. dashboard 可以把“质量回归”和“artifact 不可信”分开展示。

验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：`45 passed`

新的任务缺口：

1. diagnosis/repair task 需要把 `baseline_untrusted/current_untrusted` 作为结构化字段继承下去。
2. `gate.md` 和 `comparison.md` 仍可继续增加 subject 统计和失败 subject 明细。
3. attestation 仍未签名，需要接入签名策略。
4. targeted eval stub、materialized suite、repair plan 输出目录仍需生成自己的 attestation。

## 最新进展：Iteration 110

本轮把 run attestation 可信度接入 `eval compare`。第109轮已经让 release gate 强制复算 `run-attestation.json` 的 subject digest，但跨 run 比较仍可能在 baseline/current 其中一侧产物已被篡改、缺失或半迁移时继续解释质量差异。本轮目标是：比较两个 run 之前先判断 run bundle 是否可信，避免把 artifact 损坏误判成模型或 harness 行为变化。

已完成：

1. `compare_eval_runs()` 新增 `attestation_diff`。
2. `attestation_diff` 记录：
   - `baseline_present`
   - `current_present`
   - `baseline_failures`
   - `current_failures`
   - `comparison_attestation_failures`
3. compare 复用 `verify_run_attestation(run_dir)`：
   - 如果双方都没有 attestation，按 legacy comparison 兼容处理，不额外制造回归；
   - 如果一侧有 attestation、另一侧缺失，则缺失侧被标记为不可信；
   - 如果某侧 attestation 存在但 digest/size/required subject 校验失败，则该侧被标记为不可信。
4. release/strict profile 新增回归原因：
   - `attestation_untrusted`
5. `regression_reason_links` 对 `attestation_untrusted` 记录具体失败列表。
6. comparison Markdown 新增 `## Artifact Attestation`：
   - baseline attestation 是否存在；
   - current attestation 是否存在；
   - attestation 失败列表。
7. repair/diagnosis 链路可继承 `attestation_untrusted` reason，并给出建议：
   - 先修复 run bundle 可审计性，再解释质量回归。
8. 单测覆盖：
   - current `eval-report.json` 被篡改后，compare 报告 digest mismatch 和 size mismatch；
   - baseline 有 attestation、current 缺失 attestation 时，release comparison 被 `attestation_untrusted` 阻断；
   - legacy 双方都没有 attestation 的旧 comparison 不被强制改判。

对 harness 的意义：

1. compare 不再把不可信 run 当作可解释质量信号。
2. release/strict 比较路径可以区分“模型变差”和“输入 run bundle 已损坏/缺证据”。
3. 这对长期小模型优化很关键：历史 run 会被复制、上传、下载、合并、清理、局部重跑，compare 必须能先发现 artifact 层面的不可信。
4. Metis 的 eval 链路进一步形成闭环：
   - report 写出 attestation；
   - gate 验证 attestation；
   - compare 识别 attestation trust failure；
   - diagnosis/repair 能把 trust failure 作为独立修复任务。

验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：`45 passed`

新的任务缺口：

1. `gate.md` 和 `comparison.md` 需要更详细的 attestation subject 统计，而不是只列失败字符串。
2. diagnosis/repair task 可以把 `attestation_untrusted` 映射到专门的 artifact repair owner area。
3. attestation 仍未签名，需要接入 Sigstore/GitHub artifact attestation 或本地签名策略。
4. targeted eval stub、materialized suite、repair plan 输出目录也应生成自己的 attestation。
5. compare 可进一步输出 `baseline_untrusted`、`current_untrusted` 两个更明确的顶层布尔字段。

## 最新进展：Iteration 109

本轮把第108轮新增的 `run-attestation.json` 接入 release gate。第108轮已经能为 run 目录生成 in-toto/SLSA 风格的 artifact digest 清单，但如果 gate 不读取并复算这些 digest，attestation 仍只是“写出来的说明文件”，还没有变成强制可信边界。本轮目标是让发布级评测不能绕过产物完整性验证。

已完成：

1. 新增 `verify_run_attestation(run_dir)`：
   - 检查 `run-attestation.json` 是否存在；
   - 检查 JSON 是否可解析；
   - 检查 `_type` 是否为 `https://in-toto.io/Statement/v1`；
   - 检查 `predicateType` 是否为 Metis eval run attestation predicate；
   - 检查 `subject` 是否为非空列表；
   - 检查 subject 条目是否为对象；
   - 检查 subject name 是否存在；
   - 拒绝把 `run-attestation.json` 或 `run-attestation.md` 递归纳入 subject；
   - 检查 subject 是否重复；
   - 检查 subject 声明的文件是否真实存在；
   - 复算每个 subject 文件的 SHA256；
   - 复算每个 subject 文件的 size bytes；
   - 要求 `manifest.json`、`eval-report.json`、`task-specs.json` 必须出现在 subject 中。
2. `evaluate_eval_run_gate()` 新增并默认启用：
   - `require_run_attestation_evidence=True`
3. release gate 现在会把 attestation 校验失败纳入 `failures`。
4. gate JSON 输出新增：
   - `require_run_attestation_evidence`
5. CLI `metis eval gate --run ...` 显式传入：
   - `require_run_attestation_evidence=True`
6. 兼容 legacy run：
   - 可通过 `evaluate_eval_run_gate(..., require_run_attestation_evidence=False)` 关闭该要求；
   - 但 CLI release path 保持强制启用。
7. 单测覆盖：
   - 缺少 `run-attestation.json` 时 gate 失败；
   - 篡改 `eval-report.json` 后 gate 复算 digest 并失败；
   - legacy run 可显式关闭 attestation 要求；
   - CLI 显式传入 attestation gate 开关；
   - attestation verifier 的结构、digest、size、缺失主体等路径。

对 harness 的意义：

1. run bundle 不再只是“生成过 digest 清单”，而是在 release gate 上被强制验真。
2. 小模型 eval 的失败样本、报告、任务契约和 manifest 在复制、上传、同步后可以被本地 gate 重新验证。
3. 这为后续 GitHub artifact attestation、Sigstore 签名、跨机器复现实验、dashboard ingestion 建立了最小可信入口。
4. 对 9B 模型特别重要：小模型改进依赖大量历史 run 与 targeted eval。如果历史 run 被手工改过、复制损坏或缺关键文件，gate 会在回归判断之前先阻断不可信输入。

验证：

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_run_attestation.py tests\unit\test_cli_eval.py -q`：`60 passed`

新的任务缺口：

1. `eval compare` 应报告 missing attestation、attestation digest drift、baseline/current 哪一侧不可信。
2. `run-attestation.json` 还没有签名，后续可接入 Sigstore 或 GitHub artifact attestation。
3. targeted eval stub、materialized suite、repair plan 输出目录也应生成自己的 attestation。
4. gate report markdown 可以进一步列出 attestation subject 数、失败 subject、必需 artifact 覆盖情况。
5. run attestation predicate 需要 version migration 策略，避免未来 schema 扩展破坏旧 run。
6. trace export 仍需提供 OpenTelemetry-compatible JSON 视图，把 pre-run anchor 和 attestation subject 映射为 resource/span attributes。

## 最新进展：Iteration 108

本轮新增 run-level artifact attestation。前面几轮已经让 pre-run contract/provenance anchor 贯穿 manifest、gate、compare、timeline、diagnosis、repair task、targeted eval stub 和 materialized suite，但 run 目录本身仍缺一个统一的 artifact digest 清单。也就是说，外部工具想验证一个 run bundle，需要逐个打开文件并自己计算摘要。

已完成：

1. 新增 `metis/evals/attestation.py`。
2. 新增 `build_run_attestation(run_dir, manifest=None)`：
   - 扫描 run 目录下所有文件；
   - 排除 `run-attestation.json` 和 `run-attestation.md`，避免递归自引用；
   - 为每个 artifact 记录：
     - relative artifact name；
     - `digest.sha256`；
     - `size_bytes`。
3. 新增 `write_run_attestation(run_dir, manifest=None)`：
   - 写出 `run-attestation.json`；
   - 写出 `run-attestation.md`。
4. attestation 采用 in-toto/SLSA 风格的基础结构：
   - `_type: https://in-toto.io/Statement/v1`
   - `predicateType: https://metis.local/attestations/eval-run/v1`
   - `subject: [...]`
   - `predicate: {...}`
5. predicate 记录：
   - builder id；
   - run dir；
   - suite；
   - run name；
   - task contract hash；
   - provenance hash；
   - pre-run contract path；
   - pre-run contract sha256；
   - pre-run provenance hash；
   - artifact count。
6. real-small-model 报告写入流程自动生成 run attestation。
7. generic run-suite 报告写入流程自动生成 run attestation。
8. `metis.evals` 公开导出：
   - `build_run_attestation`
   - `run_attestation_to_markdown`
   - `write_run_attestation`
9. 单测覆盖：
   - subject digest 与真实文件字节 SHA256 一致；
   - attestation 不把自身递归纳入 subject；
   - real-small-model 和 generic run-suite 自动写出 attestation；
   - pre-run contract digest 被纳入 subject。

对 harness 的意义：

1. eval run 目录成为可验证 artifact bundle。
2. 外部 CI、dashboard、release gate 或 GitHub artifact 上传前，可以只读取 `run-attestation.json` 来验证关键产物完整性。
3. 这把 Metis 从“每个文件各自可信”推进到“整个 run bundle 可审计”。
4. 对 9B 小模型非常关键：小模型优化依赖大量失败样本和回归样本，如果 run bundle 在复制/上传/下载中被破坏，attestation 能提供最直接的完整性检查入口。

验证：

- `python -m pytest tests\unit\test_run_attestation.py tests\unit\test_eval_suite_run.py -q`：`20 passed`

新的任务缺口：

1. release gate 应验证 `run-attestation.json` 的 subject digest 与实际文件一致。
2. compare 应报告 attestation digest drift 或 missing attestation。
3. `run-attestation.json` 还没有签名，后续可接入 Sigstore/GitHub artifact attestation。
4. materialized eval suite 和 targeted eval stubs 的输出目录也应生成 attestation。
5. trace export 仍需提供 OpenTelemetry-compatible JSON 视图，把 pre-run anchor 映射为 resource/span attributes。

## 最新进展：Iteration 107

本轮把 repair task 的 `run_metadata` 继续传入 targeted eval stubs 和 materialized eval suite。第106轮已经让 repair task 携带失败来源 run contract anchor，但当 repair task 被转换为 targeted eval stub、再被 materialize 成可运行 suite 时，这组 anchor 会丢失。这样后续看到回归样本时，只知道它来自某个 repair task，不知道它源自哪个 pre-run contract/provenance。

已完成：

1. `build_eval_stubs_from_repair_tasks()` 生成的 stub 现在保留：
   - `run_metadata`
2. `eval_stubs_to_markdown()` 现在展示 run metadata anchor。
3. `materialize_eval_suite_from_stubs()` 的 task wrapper 现在保留：
   - `run_metadata`
4. `eval_suite_to_markdown()` 现在展示 materialized task 的 run metadata anchor。
5. 单测覆盖：
   - repair task -> targeted eval stub 的 `run_metadata` 保留；
   - targeted eval stub -> materialized suite task wrapper 的 `run_metadata` 保留；
   - Markdown 报告能展示 `pre_run_contract_sha256`。

对 harness 的意义：

1. 从失败 trace 生成的新回归样本不再丢失来源 contract。
2. 小模型后续执行 targeted eval 时，测试样本可以追溯到原始失败 run 的 pre-run contract、provenance hash 和 task contract hash。
3. 这让 Metis 的自改进闭环更可审计：
   - eval failure
   - timeline run metadata
   - diagnosis
   - repair task
   - targeted eval stub
   - materialized suite
4. 未来 `run-attestation.json` 可以把这条 lineage 统一成可验证 artifact graph。

验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：`43 passed`

新的任务缺口：

1. `run-attestation.json` 应统一列出 manifest、pre-run contract、task specs、reports、failure artifacts、timeline artifacts、stubs、materialized suite 的 digest。
2. materialized suite validator 可增加 source run metadata schema 检查。
3. trace export 仍需提供 OpenTelemetry-compatible JSON 视图，把 pre-run anchor 映射为 resource/span attributes。
4. compare 可以进一步区分 `baseline_untrusted` 与 `current_untrusted`。
5. generic suites 仍需要 suite-scoped latest pointer，避免不同套件争用全局 latest。

## 最新进展：Iteration 106

本轮把失败 timeline 的 `run_metadata` 继续传入 comparison diagnosis 和 repair task。第105轮已经让 timeline 携带 pre-run contract anchor，但 diagnosis/repair task 仍只继承 timeline path、event ids、critical event ids 和 schema repair hint events。自动修复任务仍需要再次打开 timeline 才知道这个失败属于哪个 pre-run contract、哪个 task contract、哪个 provenance hash。

已完成：

1. `eval_run_comparison_diagnosis()` 现在会从 reason link 的 timeline paths 读取 timeline 顶层 `run_metadata`。
2. 每个 diagnosis entry 新增：
   - `run_metadata`
3. `build_repair_tasks_from_diagnosis()` 现在把 diagnosis entry 的 `run_metadata` 原样写入 repair task。
4. `diagnosis.md` 现在展示 run metadata anchor，重点包括：
   - `pre_run_contract_sha256`
   - `pre_run_provenance_hash`
   - `provenance_hash`
   - `task_contract_hash`
5. 新增测试覆盖：timeline -> diagnosis -> repair task 的 run metadata 传递链路。

对 harness 的意义：

1. repair task 不再只是“去看这个 timeline”，而是直接携带可验证 run contract。
2. 后续自动修复、targeted eval stub、repair plan、attestation 都可以从 repair task 读取 contract anchor。
3. 这减少了小模型二次诊断负担：9B 模型不需要重新在文件系统里定位 run manifest/pre-run contract，它拿到的 repair payload 已经包含足够的审计上下文。
4. 这一步把 trace-driven debugging 继续推进到 trace-to-remediation：失败事件、关键 event id、hint event、run contract 都进入同一张 repair task。

验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：`43 passed`

新的任务缺口：

1. targeted eval stubs 应继承 repair task 的 `run_metadata`，保留原始 contract anchor。
2. materialized eval suite 应保留 source repair task 的 run metadata。
3. `run-attestation.json` 应统一列出 manifest、pre-run contract、task specs、failure artifacts 和 timeline artifacts 的 digest。
4. trace export 仍需提供 OpenTelemetry-compatible JSON 视图，把 pre-run anchor 映射为 resource/span attributes。
5. compare 可以进一步区分 `baseline_untrusted` 与 `current_untrusted`。

## 最新进展：Iteration 105

本轮把 pre-run contract anchor 写入失败 timeline/trace metadata。此前第103轮和第104轮已经让 manifest/latest、gate、compare 都能识别和验证 `pre-run-contract.json`，但失败 timeline 仍然只包含 task/event 级信息。诊断、repair task、CLI trace review 在打开某个失败 trace 时，看不到这个失败属于哪个 pre-run contract、哪个 task contract 和哪个 provenance hash。

已完成：

1. 新增 `annotate_failure_timelines(output_dir, run_metadata)`：
   - 读取 `<run-dir>/failures/index.json`；
   - 找到每个失败任务的 timeline JSON；
   - 写入顶层 `run_metadata`；
   - 重新生成对应 timeline Markdown。
2. real-small-model 报告写入流程在 manifest 生成后回填失败 timeline run metadata。
3. generic run-suite 报告写入流程在 manifest 生成后回填失败 timeline run metadata。
4. timeline `run_metadata` 现在包含：
   - `suite`
   - `run_name`
   - `requested_run_name`
   - `suite_definition_type`
   - `schema_version`
   - `suite_schema_id`
   - `suite_schema_path`
   - `suite_schema_sha256`
   - `task_contract_hash`
   - `provenance_hash`
   - `pre_run_contract_path`
   - `pre_run_contract_sha256`
   - `pre_run_provenance_hash`
5. failure timeline Markdown 现在显示 pre-run contract path/hash、pre-run provenance hash、post-run provenance hash、task contract hash 和 suite schema hash。
6. `metis trace show` 使用的 timeline renderer 也显示同样的 run metadata anchor。
7. 单测覆盖：
   - real-small-model 失败 timeline 写入 pre-run contract anchor；
   - generic run-suite 失败 timeline 写入 pre-run contract anchor；
   - CLI/telemetry timeline Markdown 渲染 run metadata anchor。

对 harness 的意义：

1. 失败 trace 不再是孤立事件流，而是携带完整 run contract identity。
2. 小模型 repair task 可以从具体失败事件直接回溯到 pre-run contract、task contract 和 provenance，而不用重新猜测 run 目录。
3. 这让 Metis 的诊断链路更接近生产级 agent observability：每条失败 timeline 都能证明“这次失败在什么 contract 下发生”。
4. 未来生成自动 repair task、attestation、dashboard 时，可以直接从 timeline 提取 run-level anchor。

验证：

- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_eval_runner.py tests\unit\test_timeline.py tests\unit\test_cli_eval.py -q`：`100 passed`

新的任务缺口：

1. diagnosis/repair task 应把 timeline `run_metadata` 提取到 repair payload。
2. `run-attestation.json` 应统一列出 manifest、pre-run contract、task specs、failure artifacts 和 timeline artifacts 的 digest。
3. trace export 仍需提供 OpenTelemetry-compatible JSON 视图，把 pre-run anchor 映射为 resource/span attributes。
4. compare 可以进一步区分 `baseline_untrusted` 与 `current_untrusted`。
5. generic suites 仍需要 suite-scoped latest pointer，避免不同套件争用全局 latest。

## 最新进展：Iteration 104

本轮把第103轮新增的 pre-run contract manifest anchor 接入 `eval compare`。此前 release gate 已会校验 manifest 中声明的 `pre_run_contract_path`、`pre_run_contract_sha256`、`pre_run_provenance_hash`，但 compare 只校验 pre-run contract 的业务内容与 manifest 是否一致，没有校验 manifest 声明的文件摘要是否真的匹配磁盘文件。

已完成：

1. `load_eval_run()` 现在读取 `<run-dir>/pre-run-contract.json` 时会同时计算真实文件 SHA256。
2. `compare` 的 pre-run/post-run mismatch 检测新增三类锚点校验：
   - manifest `pre_run_contract_path` 是否等于实际 pre-run contract 路径；
   - manifest `pre_run_contract_sha256` 是否等于实际文件 SHA256；
   - manifest `pre_run_provenance_hash` 是否等于 pre-run contract 内的 `provenance_hash`。
3. release 和 strict profile 继续使用已有 `pre_run_post_run_mismatch` reason 阻断不可信比较。
4. 新增测试覆盖：pre-run contract 内容与 manifest 业务字段一致，但 manifest 声明的 `pre_run_contract_sha256` 被篡改时，compare 仍会失败。

对 harness 的意义：

1. compare 不再只判断“contract 内容和 manifest 字段一致”，还会判断“manifest 声明的 contract 文件身份是否真实”。
2. 这使 Metis 的比较逻辑更接近 artifact attestation 的验证模型：subject artifact 的 digest 必须和实际 artifact 内容一致。
3. 对跨电脑同步、GitHub 拉取、历史 run 复用尤其重要，因为 run 目录可能被复制、合并或手工修复；compare 必须能拒绝摘要不可信的运行结果。

验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：`42 passed`

新的任务缺口：

1. trace export 仍需写入 `pre_run_contract_sha256` 和 `pre_run_provenance_hash`。
2. diagnosis/repair task 应把 pre-run contract anchor 加入 provenance 类 reason links。
3. `run-attestation.json` 应统一列出 manifest、pre-run contract、task specs、failure artifacts 的 digest。
4. compare 可以进一步区分 `baseline_untrusted` 与 `current_untrusted`，输出更明确的发布建议。
5. generic suites 仍需要 suite-scoped latest pointer，避免不同套件争用全局 latest。

## 最新进展：Iteration 103

本轮把 pre-run contract 从“单独文件”提升为 run manifest/latest pointer 的一等审计锚点，并让 release gate 校验这个锚点。第102轮 compare 已经能发现 pre-run/post-run 内容不一致，但 manifest/latest 本身还没有记录 pre-run contract 文件路径和文件摘要，trace、dashboard、外部 CI 读取 manifest 时无法直接定位和验证 pre-run artifact。

已完成：

1. real-small-model manifest/latest 新增：
   - `pre_run_contract_path`
   - `pre_run_contract_sha256`
   - `pre_run_provenance_hash`
2. generic run-suite manifest/latest 新增同样三项字段。
3. `pre_run_contract_sha256` 使用真实 `pre-run-contract.json` 文件字节计算 SHA256，而不是示例值或 payload 内字段。
4. 如果报告写入时 pre-run contract 尚不存在，manifest/latest 仍写入预期路径，但 hash/provenance hash 留空，便于 gate 暴露缺口。
5. release gate 现在额外校验：
   - manifest `pre_run_contract_path` 是否等于实际 run 目录下的 `pre-run-contract.json`；
   - manifest `pre_run_contract_sha256` 是否等于真实文件 SHA256；
   - manifest `pre_run_provenance_hash` 是否等于 pre-run contract 内的 `provenance_hash`。
6. 单测覆盖 real-small-model 和 generic run-suite 的 manifest/latest anchor 写入，以及 gate 对锚点字段的验证。

对 harness 的意义：

1. pre-run contract 不再只是 run 目录里的旁路文件，而是 manifest/latest 公开声明的可验证 subject artifact。
2. 后续 trace export、dashboard、CI gate 和 repair plan 可以只读取 manifest/latest，就能找到并校验 pre-run contract。
3. 这符合 artifact provenance 的核心思想：把 subject artifact 的 digest 和声明绑定起来，降低跨机器拷贝、人工修改、断点续跑造成的审计失真。
4. 对 9B/flash 模型尤其重要，因为小模型优化依赖大量历史 eval；只有每个 eval 的输入 contract 可定位、可验真，回归比较才可信。

验证：

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_eval_suite_run.py -q`：`34 passed`

新的任务缺口：

1. trace export 仍需写入 `pre_run_contract_sha256` 和 `pre_run_provenance_hash`。
2. compare 应校验 manifest 声明的 pre-run contract SHA256 是否匹配实际文件。
3. diagnosis/repair task 应把 pre-run contract anchor 加入 provenance 类 reason links。
4. latest pointer 仍是全局 latest，generic suites 需要 suite-scoped latest pointer。
5. 需要一个 artifact attestation 风格的 `run-attestation.json`，把 manifest、pre-run contract、task specs、failure artifacts 的 digest 统一列出。

## 最新进展：Iteration 102

本轮把 `eval compare` 接入 pre-run contract 与 post-run manifest 的一致性审计。此前 release gate 已能拒绝单个 run 的 pre-run/post-run 不一致，但跨版本比较仍只看两个 run 的最终 `manifest.json`。这意味着一个 run 可能在真实 provider 调用前写了正确 contract，后续 manifest 又被错误逻辑、手工改动或失败恢复流程写成另一套 provenance，compare 仍可能把它当成有效基线或当前结果。

已完成：

1. `load_eval_run()` 现在会在存在时读取 `<run-dir>/pre-run-contract.json`。
2. `provenance_diff` 新增：
   - `baseline_pre_run_post_run_mismatches`
   - `current_pre_run_post_run_mismatches`
   - `pre_run_post_run_mismatches`
3. compare 现在校验：
   - pre-run `provenance_hash` 是否匹配 pre-run provenance payload；
   - pre-run `provenance_hash` 是否匹配 post-run manifest；
   - pre-run `task_contract_hash` 是否匹配 post-run manifest；
   - pre-run `task_spec_hash_summary` 是否匹配 post-run manifest。
4. `comparison.md` 的 `## Provenance Drift` 增加 `Pre-run/post-run mismatches`。
5. release 和 strict profile 都会把 `pre_run_post_run_mismatch` 作为 regression reason。
6. regression reason links 会携带具体 mismatch 列表，诊断和 repair plan 可以继续消费。
7. compare 对旧 run 兼容：缺少 `pre-run-contract.json` 不直接失败；只有 pre-run contract 存在但和 manifest 不一致时才阻断。

对 harness 的意义：

1. 比较不再只判断“两个最终 manifest 是否不同”，还会判断“每个 run 自己是否可信”。
2. 小模型优化依赖大量低成本、多轮次 eval。如果某次 run 的 contract 和 manifest 不一致，它的成功率、失败簇、repair 任务都不能作为可靠依据。
3. 这把 Metis 的 eval 链路推进到“先声明、后执行、再校验、再比较”的闭环，适合作为跨场景 agent harness 的基础设施。

验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：`41 passed`

新的任务缺口：

1. trace export 应加入 pre-run provenance hash 和 contract path。
2. compare 可以继续区分“baseline 不可信”和“current 不可信”，给出不同 release 建议。
3. gate 和 compare 的 provenance mismatch 诊断码需要统一，便于自动 repair task 生成。
4. run artifact manifest 应记录 pre-run contract path/hash，减少工具查找成本。
5. eval dashboard 应把 pre-run/post-run mismatch 作为单独的红色审计状态。

## 最新进展：Iteration 091

本轮补齐独立 release gate 的 schema evidence 审计链路。此前 `run-suite --gate` 已经会在模型调用前拒绝未声明 `schema_version` 的 suite，generic eval run 也会把 suite schema snapshot metadata 写入 `manifest.json`。但是独立命令 `metis eval gate --run <run-dir>` 只检查运行结果、失败任务、schema violation、failure cluster 和 remediation backlog，没有强制证明这个 run manifest 来自哪个 suite schema artifact。

已完成：

1. `evaluate_eval_run_gate()` 默认要求 run manifest 包含：
   - `suite_schema_id`
   - `suite_schema_sha256`
2. 缺失证据时 gate 直接失败，并输出明确失败原因：
   - `suite_schema_id missing from manifest`
   - `suite_schema_sha256 missing from manifest`
3. gate JSON 结果新增：
   - `require_suite_schema_evidence`
   - `run.suite_schema_id`
   - `run.suite_schema_sha256`
4. gate markdown 报告新增 suite schema id/hash，便于人工审查 release artifact。
5. CLI `metis eval gate --run ...` 显式传入 `require_suite_schema_evidence=True`，避免命令行 release path 依赖隐含默认值。
6. Python API 保留 `require_suite_schema_evidence=False`，仅用于有意识的 legacy run 分析，不作为 CLI 默认能力暴露。

对 harness 的意义：

1. 通过 gate 的 run 不能只证明“任务结果达标”，还必须证明“这批结果是在某个确定 suite schema contract 下生成的”。
2. 未来针对不同场景开发 agent 时，评测结果可以跨仓库、跨电脑、跨时间审计，不会因为 run 目录被复制或手工组装而丢失 schema 依据。
3. 对 9B/flash 小模型尤其重要，因为小模型质量优化依赖大量回归样本；如果样本的 suite contract 不可追溯，后续比较和诊断会失真。

验证：

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py -q`：`46 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. real-small-model suite manifest 仍需加入 schema evidence 或明确声明它不是 loadable generic suite。
2. suite version/migration 需要专用异常、诊断码和更细的用户提示。
3. suite-level `tool_schemas` 仍需设计，避免 per-task schema 重复导致维护漂移。
4. suite-local tool schema 合法性检查还需要扩展。
5. gate report 可以继续记录 validation report path/hash，形成更完整的 provenance chain。

## 最新进展：Iteration 092

本轮修复 real-small-model 内置评测路径的 provenance 缺口。第091轮让独立 `eval gate` 默认要求 manifest 中存在 `suite_schema_id` 和 `suite_schema_sha256`，这会暴露一个真实问题：`metis eval real-small-model --gate` 的 suite 是代码定义的，不是 JSON suite 文件加载的，因此此前没有写入 suite schema evidence。

已完成：

1. `real_small_model_eval_metadata()` 新增：
   - `suite_definition_type: code-defined-builtin`
   - `schema_version: code-defined`
   - `suite_schema_id`
   - `suite_schema_path`
   - `suite_schema_sha256`
2. `real_small_model_eval_manifest()` 顶层写入：
   - `suite_definition_type`
   - `schema_version`
   - `suite_schema_id`
   - `suite_schema_path`
   - `suite_schema_sha256`
3. `write_real_small_model_eval_latest_pointer()` 写入：
   - `suite_definition_type`
   - `schema_version`
   - `suite_schema_id`
   - `suite_schema_sha256`
4. 新增测试覆盖 real-small-model metadata、manifest、latest pointer 的 schema evidence 写入。

设计判断：

1. real-small-model 不是 file-loaded generic suite，因此不应伪装成 `"schema_version": "1"`。
2. 它应声明为 `"schema_version": "code-defined"`，同时绑定当前 `suite-schema-v1.json` 的 id/path/hash。
3. 这样既不欺骗来源，又能让 release gate 有完整 schema provenance。

验证：

- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_cli_eval.py tests\unit\test_eval_gate.py -q`：`58 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. code-defined suites 应生成 task contract manifest，包含任务 id、task spec hash、suite schema hash。
2. eval compare 应把 suite definition type 或 schema hash 变化识别为 provenance drift。
3. gate report 应继续加入 validation report path/hash。
4. latest pointer 应加入 task spec hash summary，避免只知道 schema，不知道实际内置任务集是否变化。

## 最新进展：Iteration 093

本轮把 task contract identity 提升为 run provenance 的一等字段。此前 `EvalSuiteResult.write_reports()` 已经会写 `task-specs.json`，但 `manifest.json` 和 `latest.json` 只有 schema evidence，没有 suite-level task contract hash。这样 dashboard、release gate 或快速审查只能看到 schema，不能直接证明这次 run 到底跑的是哪组任务契约。

已完成：

1. `EvalSuiteResult` 新增：
   - `task_spec_hash_summary()`
   - `task_contract_hash()`
2. `task-specs.json` 新增：
   - `task_contract_hash`
   - `task_spec_hash_summary`
3. generic eval `manifest.json` 和 `latest.json` 新增：
   - `task_contract_hash`
   - `task_spec_hash_summary`
4. real-small-model `manifest.json` 和 `latest.json` 新增：
   - `task_contract_hash`
   - `task_spec_hash_summary`
5. 测试覆盖 runner、generic suite report、real-small-model report 的 task contract hash 写入。

外部检索结论：

1. OpenTelemetry GenAI 方向强调模型调用、工具调用、token 和 trace 语义要结构化。
2. MLflow dataset/evaluation lineage 方向强调 schema、dataset identity、evaluation artifact 的可追溯。
3. AgentAssay 一类 agent regression 研究强调 trace-first、behavioral fingerprint、CI gate。
4. 对 Metis 来说，run artifact 必须证明 model/profile、suite schema、task contract、trace/failure artifact 和 gate result，而不是只证明 pass/fail。

验证：

- `python -m pytest tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_compare.py -q`：`86 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. `eval compare` 应直接读取 manifest/latest 中的 `task_contract_hash`，并显式报告顶层 task contract drift。
2. `eval gate` 应可要求 release run 具备非空 task contract evidence。
3. code-defined suite 应在真实模型调用前写出 pre-run contract artifact。
4. trace export 应把 task contract hash 映射到 OTel-compatible attribute。
5. task contract hash 与 suite schema hash 应形成 combined provenance hash，用于 release artifact 快速验真。

## 最新进展：Iteration 094

本轮让 `eval compare` 直接消费第093轮写入 manifest/latest 的 `task_contract_hash`。此前 compare 能从 `task-specs.json` 或失败 artifact 中检测 per-task hash drift，但没有把 manifest 顶层 suite-level task contract hash 作为一等比较信号。

已完成：

1. `compare_eval_runs()` 将 baseline/current manifest 中的 task contract hash 传入 task spec diff。
2. `_task_spec_hash_summary()` 优先读取 `task-specs.json.task_spec_hash_summary`，兼容旧的 `tasks[].task_spec_hashes`。
3. 新增 `_task_contract_hash()`：
   - 优先读取 `manifest.json.task_contract_hash`
   - 回退读取 `task-specs.json.task_contract_hash`
4. `task_spec_diff` 新增：
   - `baseline_task_contract_hash`
   - `current_task_contract_hash`
   - `task_contract_hash_changed`
5. Markdown 新增 `Task contract hash changed`。
6. strict profile 将 `task_contract_hash_changed` 作为 regression reason。
7. reason links 包含 task contract hash drift payload。

验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：`39 passed`

新的任务缺口：

1. `eval gate` 应要求 release run 具备非空 task contract evidence。
2. `eval diagnose` 应对 task contract drift 生成专门的修复/审查任务。
3. 应构建 combined provenance hash：suite schema hash + task contract hash + profile + tool inventory hash。
4. real-small-model 应在调用真实模型前写出 pre-run contract artifact。

## 最新进展：Iteration 095

本轮把 task contract evidence 接入 release gate。此前 `metis eval gate --run <run-dir>` 已经要求 suite schema evidence，但仍可通过缺少顶层任务契约证据的 run。现在 gate 默认要求 manifest 中同时存在 `task_contract_hash` 和非空 `task_spec_hash_summary`。

已完成：

1. `evaluate_eval_run_gate()` 新增默认严格参数：
   - `require_task_contract_evidence=True`
2. 缺失任务契约证据时 gate 失败：
   - `task_contract_hash missing from manifest`
   - `task_spec_hash_summary missing from manifest`
3. gate result 新增：
   - `require_task_contract_evidence`
   - `run.task_contract_hash`
   - `run.task_spec_hash_summary`
4. gate Markdown 新增：
   - `Task contract hash`
   - `Task spec hash summary count`
5. CLI 显式传入：
   - `require_suite_schema_evidence=True`
   - `require_task_contract_evidence=True`
6. Python API 保留 legacy analysis 逃生口：
   - `require_task_contract_evidence=False`

验证：

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py -q`：`48 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 构建 combined provenance hash：suite schema hash + task contract hash + model/profile + tool inventory hash。
2. gate 后续应要求 combined provenance evidence。
3. real-small-model 应在真实 provider 调用前写 pre-run contract artifact。
4. `eval diagnose` 应为 task contract drift 生成专门审查任务。

## 最新进展：Iteration 096

本轮新增 combined eval provenance hash。此前 release gate 已经要求 suite schema evidence 和 task contract evidence，但自动化仍需要读取多个字段才能判断两个 run 是否可比较。本轮引入统一的 `provenance` payload 和 `provenance_hash`。

已完成：

1. 新增 `metis.evals.provenance`：
   - `stable_json_hash()`
   - `tool_inventory_hash()`
   - `eval_provenance_payload()`
   - `eval_provenance_hash()`
2. generic eval metadata 新增：
   - `tool_inventory_hash`
3. real-small-model metadata 新增：
   - `tool_inventory_hash`
4. generic eval manifest/latest 新增：
   - `provenance`
   - `provenance_hash`
5. real-small-model manifest/latest 新增：
   - `provenance`
   - `provenance_hash`
6. provenance payload 包含：
   - suite
   - suite definition type
   - schema version
   - suite schema sha256
   - task contract hash
   - model
   - base url
   - profile
   - tool inventory hash

验证：

- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_eval_runner.py -q`：`49 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. `eval gate` 应要求 `provenance_hash` 和完整 provenance payload。
2. `eval compare` 应直接报告 `provenance_hash` drift。
3. `eval diagnose` 应为 provenance-only drift 生成专门审查任务。
4. code-defined suites 应在真实 provider 调用前写 pre-run provenance contract artifact。

## 最新进展：Iteration 097

本轮让 release gate 强制检查 combined provenance evidence。此前 manifest/latest 已经写入 `provenance` 和 `provenance_hash`，但 gate 尚未验证它们。现在 `metis eval gate --run` 默认要求 provenance payload 存在、hash 存在、hash 与 payload 匹配，并检查关键字段完整。

已完成：

1. `evaluate_eval_run_gate()` 新增：
   - `require_provenance_evidence=True`
2. gate 检查：
   - non-empty `provenance`
   - `provenance_hash`
   - `provenance_hash == eval_provenance_hash(provenance)`
3. provenance payload 必须包含：
   - suite
   - suite schema sha256
   - task contract hash
   - model
   - base url
   - profile
   - tool inventory hash
4. CLI 显式传入：
   - `require_provenance_evidence=True`

## 最新进展：Iteration 098

本轮让 `eval compare` 直接消费 `provenance_hash`。如果 baseline/current 的 provenance hash 不一致，release 和 strict profile 都会报告 `provenance_hash_changed`，比较报告也会列出具体 provenance 字段变化。

已完成：

1. `compare_eval_runs()` 新增 `provenance_diff`。
2. `provenance_diff` 包含：
   - baseline/current provenance hash
   - `provenance_hash_changed`
   - `field_changes`
3. Markdown 新增：
   - `## Provenance Drift`
4. release/strict profile 新增 regression reason：
   - `provenance_hash_changed`
5. reason links 包含 provenance hash change 和字段变化。

验证：

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py -q`：`92 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. `eval diagnose` 应为 provenance drift 生成专门 review task。
2. real-small-model 应在真实 provider 调用前写 pre-run provenance contract artifact。
3. trace export 应把 provenance hash 写入 run-level event 或 OTel resource/span attributes。

## 最新进展：Iteration 099

本轮把 real-small-model 的 provenance 从 post-run manifest 推进到 pre-run contract artifact。此前真实 provider 调用发生在报告写入之前，如果调用失败或中断，本地不会留下“这次原本准备跑什么”的 contract。现在 CLI 和 `run_and_write_real_small_model_eval_suite()` 都会在 provider 调用前写出 pre-run contract。

已完成：

1. 新增 `real_small_model_pre_run_contract()`：
   - code-defined task list
   - metadata
   - full task specs
   - task spec hash summary
   - task contract hash
   - provenance
   - provenance hash
2. 新增 `pre_run_contract_to_markdown()`。
3. 新增 `write_real_small_model_pre_run_contract()`：
   - `pre-run-contract.json`
   - `pre-run-contract.md`
4. `run_and_write_real_small_model_eval_suite()`：
   - run name 只解析一次；
   - provider 调用前写 pre-run contract；
   - final reports 写入同一个 resolved run directory。
5. CLI `metis eval real-small-model`：
   - provider 调用前写 pre-run contract；
   - 输出 pre-run contract 目录；
   - final reports 复用同一个 resolved run name。

验证：

- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_cli_eval.py -q`：`51 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. generic `run-suite` 也应写 pre-run contract。
2. post-run manifest 应链接 pre-run contract path/hash。
3. gate 应验证 post-run manifest provenance 与 pre-run contract provenance 一致。
4. compare 应报告 pre-run/post-run provenance mismatch。

## 最新进展：Iteration 100

本轮把 pre-run contract 能力扩展到 generic `metis eval run-suite`。此前只有 real-small-model 会在 provider 调用前写 contract；现在任意 loadable eval suite 在真实模型调用前也会写出 `pre-run-contract.json` 和 `pre-run-contract.md`。

已完成：

1. 新增 `generic_eval_pre_run_contract()`：
   - suite payload
   - executable task specs
   - metadata
   - full task specs
   - task spec hash summary
   - task contract hash
   - provenance
   - provenance hash
2. 新增 generic `pre_run_contract_to_markdown()`。
3. 新增 `write_generic_eval_pre_run_contract()`。
4. `run_and_write_generic_eval_suite()`：
   - run name 只解析一次；
   - provider 调用前写 pre-run contract；
   - post-run reports 写入同一目录。
5. CLI `metis eval run-suite`：
   - provider 调用前写 pre-run contract；
   - 输出 pre-run contract 目录；
   - post-run reports 复用同一个 resolved run name。

验证：

- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_cli_eval.py -q`：`53 passed`
- `python -m compileall -q metis`：通过

新的任务缺口：

1. gate 应验证 post-run manifest provenance 与 `pre-run-contract.json` 一致。
2. compare 应报告 pre-run/post-run mismatch。
3. trace export 应写入 pre-run provenance hash。

## 最新进展：Iteration 101

本轮让 release gate 校验 pre-run contract 与 post-run manifest 的一致性。此前 real-small-model 和 generic run-suite 都会在 provider 调用前写 `pre-run-contract.json`，但 gate 还没有验证它和最终 `manifest.json` 是否一致。现在 gate 默认要求 pre-run contract 存在，并校验 provenance/task contract/task spec summary 三个核心字段。

已完成：

1. `evaluate_eval_run_gate()` 新增：
   - `require_pre_run_contract_evidence=True`
2. gate 读取：
   - `<run-dir>/pre-run-contract.json`
3. gate 失败条件新增：
   - pre-run contract 缺失；
   - pre-run provenance 缺失；
   - pre-run provenance hash 与 payload 不匹配；
   - pre-run provenance hash 与 manifest provenance hash 不一致；
   - pre-run task contract hash 与 manifest 不一致；
   - pre-run task spec hash summary 与 manifest 不一致。
4. gate result 新增：
   - `run.pre_run_contract_path`
   - `run.pre_run_provenance_hash`
   - `require_pre_run_contract_evidence`
5. gate Markdown 新增：
   - `Pre-run provenance hash`
6. CLI 显式传入：
   - `require_pre_run_contract_evidence=True`

验证：

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py -q`：`55 passed`

新的任务缺口：

1. compare 应报告 pre-run/post-run mismatch。
2. diagnose 应生成 provenance review task。
3. trace export 应加入 pre-run provenance hash。

## 最新进展：Iteration 062

本轮继续围绕“评测体系必须先证明自己是正确的”推进。Metis 已经把 `required_tool_arguments` 从普通 JSON 结构检查升级为和真实 `ToolSpec.parameters` 对齐的 schema-aware validation：

1. `generic_eval_validation_context` 现在导出 `tool_schemas`。
2. `validate_eval_suite` 现在可以在运行模型前检查 suite 中声明的工具参数字段是否存在。
3. 字面值、`equals`、`in` 谓词会按参数 schema 校验类型。
4. `contains`、`startswith`、`endswith` 会拒绝绑定到纯数值/布尔参数。
5. 这降低了“suite 写错导致模型背锅”的风险，让真实 9B/flash 评测失败更可信。

新增验证：

- `python -m pytest tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`：20 passed
- `python -m pytest tests\unit\test_cli_eval.py -q`：36 passed
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 扩展工具 schema validator，支持 `additionalProperties`、数值范围、字符串正则、数组长度等 JSON Schema 约束。
2. 给 eval suite 增加参数谓词类型系统，避免所有复杂匹配都落到字符串化 `contains`。
3. 在 `validate-suite` 报告中输出相关工具 schema 摘要，降低 suite 编写成本。
4. 把 schema-aware validation 纳入 release gate，使任何通用评测套件在真实模型调用前必须先通过契约验证。

## 最新进展：Iteration 063

本轮把工具运行时 schema guardrail 继续收紧。目标是减少 9B/flash 小模型在工具调用时常见的参数漂移，让错误尽量在工具执行前被确定性拦截，而不是进入 handler 后才变成 runtime error。

已完成：

1. `ToolArgumentSchemaValidator` 支持更多 JSON Schema 约束：
   - `additionalProperties`
   - `patternProperties`
   - `minLength`
   - `maxLength`
   - `pattern`
   - `minimum`
   - `maximum`
   - `exclusiveMinimum`
   - `exclusiveMaximum`
   - `minItems`
   - `maxItems`
2. `oneOf` 改为严格“恰好一个分支匹配”，并在无分支匹配时保留分支错误摘要。
3. 内置工具 schema 关闭额外参数。
4. `run_command` / `run_test` 阻断空命令数组。
5. timeout 参数限制为 1 到 3600。
6. `read_file` / `write_file` 的 encoding 限定为 `utf-8` 和 `utf-8-sig`。

新增验证：

- `python -m pytest tests\unit\test_tool_schema_validator.py tests\unit\test_tools.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`：45 passed
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 增加 agent loop 层 eval：模型第一次多传参数或传空命令数组，收到 schema repair feedback 后成功重试。
2. 将新的 schema failure shape 纳入 failure clustering，避免错误聚类过碎。
3. 给 `oneOf` 失败增加“最接近分支”提示，降低小模型 repair 难度。
4. 继续补 `const`、`allOf`、`anyOf`、`not`、`uniqueItems`、`minProperties`、`maxProperties`、`dependentRequired`。
5. 设计工具 schema 编译器，把复杂 JSON Schema 转成更适合小模型理解的工具说明文本。

## 最新进展：Iteration 064

本轮把严格 schema validation 推进到 repair loop 闭环。目标不是只让错误失败，而是让 9B/flash 小模型在失败后能获得明确修复动作，并在下一轮工具调用中恢复。

已完成：

1. `AgentLoop` 的 schema failure feedback 新增 `schema_repair_hints`。
2. 对常见 schema 错误生成动作型提示：
   - 删除额外参数
   - 补必填参数
   - 修正类型
   - 避免空数组
   - 调整数值边界
   - 使用合法 enum
   - 匹配字符串 pattern
   - 让 `oneOf` 恰好一个分支匹配
3. 新增 agent loop 集成测试：
   - 模型第一次多传 `url`，收到提示后删除额外参数并成功调用工具。
   - 模型第一次传 `command: []`，收到提示后改成合法命令数组并成功调用工具。
4. 既有缺必填字段 repair 测试新增对 `schema_repair_hints` 的断言。

新增验证：

- `python -m pytest tests\integration\test_agent_loop_schema_guard.py tests\unit\test_tools.py tests\unit\test_tool_schema_validator.py -q`：35 passed
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 将 schema repair hints 接入 EvalRunner 指标。
2. 在真实 9B/flash eval suite 中加入“多传参数后修复”和“空命令数组后修复”任务。
3. 把 schema repair hints 写入 trace timeline。
4. 将 schema error 字符串转成稳定分类，避免 failure shape key 过长。
5. 对 `oneOf` 计算最接近分支，生成更精确的修复建议。

## 最新进展：Iteration 065

本轮把 schema repair hints 从运行时反馈升级为评测指标。目标是让 harness 能回答：小模型收到明确 schema 修复提示后，是否真的恢复成功。

已完成：

1. 新增 `metis.tools.schema_feedback.schema_repair_hints`，统一生成 schema 修复提示。
2. `ToolDispatcher` 在 schema validation failure 时写入 `metadata["schema_repair_hints"]`。
3. `AgentLoop` 在工具反馈中继续输出 `schema_repair_hints`。
4. `EvalResult` 新增：
   - `schema_repair_hints_seen`
   - `schema_repair_hint_successes`
   - `schema_repair_hint_failures`
5. `EvalTaskSpec` 新增：
   - `min_schema_repair_hint_successes`
   - `max_schema_repair_hint_failures`
6. Eval markdown 表格、failure artifact metrics、tool result excerpts 已覆盖新指标。
7. Suite validation 已把新增 gate 字段纳入整数/非负校验。

新增验证：

- `python -m pytest tests\unit\test_eval_runner.py tests\unit\test_tools.py tests\integration\test_agent_loop_schema_guard.py tests\unit\test_eval_suite_validation.py -q`：71 passed
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 将 schema repair hint 类型稳定化，例如 `remove_additional_property`、`add_required_property`、`fix_type`、`fix_empty_array`。
2. 增加 suite-level hint recovery rate 汇总。
3. 在真实 9B/flash eval suite 中加入 hint recovery 任务。
4. failure clustering 接入 hint 类型，而不是只依赖原始 schema error 字符串。
5. trace timeline 增加独立 `schema.repair_hint` event。

## 最新进展：Iteration 066

本轮把 schema repair hints 从文本和并行数组升级为 canonical details，并接入 failure clustering。

已完成：

1. `schema_repair_feedback` 返回 `hints`、`hint_types`、`details`。
2. detail 单项包含：
   - `hint_type`
   - `schema_path`
   - `schema_keyword`
   - `schema_error`
   - `hint_text`
3. Dispatcher、AgentLoop、EvalRunner excerpts 均保留 `schema_repair_hint_details`。
4. Failure clustering 新增：
   - `schema_repair_hint_type:{hint_type}`
   - `schema_repair_hint_failure_type:{hint_type}`
   - `schema_repair_hint_path:{hint_type}:{normalized_schema_path}`
5. Failure signals 新增：
   - `schema_repair_hint_type:{hint_type}={count}`
   - `schema_repair_hint_failure_type:{hint_type}={count}`
   - `schema_repair_hint_detail={hint_type}@{schema_path}:{schema_keyword}`
6. Remediation backlog 会把 schema repair hint failure type 标记为 critical。

新增验证：

- `python -m pytest tests\unit\test_schema_feedback.py tests\unit\test_tools.py tests\integration\test_agent_loop_schema_guard.py tests\unit\test_eval_runner.py tests\unit\test_failure_clusters.py -q`：63 passed
- `python -m compileall -q metis`：通过

新的任务缺口：

1. detail parser 继续提取 `expected_type`、`actual_type`、`constraint_value`、`allowed_values`。
2. Eval markdown 增加 hint type 汇总表。
3. suite-level hint recovery rate 汇总。
4. trace timeline 增加独立 `schema.repair_hint` event。
5. 真实 9B/flash eval suite 加入 hint recovery 任务。

## 最新进展：Iteration 067

本轮把 schema repair hint 指标提升到 suite-level summary。

已完成：

1. `EvalSuiteResult.summary` 新增 run-level 汇总：
   - `schema_repair_hints_seen`
   - `schema_repair_hint_successes`
   - `schema_repair_hint_failures`
   - `schema_repair_hint_recovery_rate`
   - `schema_repair_hint_types_seen`
   - `schema_repair_hint_type_successes`
   - `schema_repair_hint_type_failures`
2. `eval-report.json` 新增顶层 `summary`。
3. `eval-report.md` 新增 `## Summary`。
4. 新增 suite summary 聚合测试，覆盖 recovery rate 和 hint type map 聚合。

新的任务缺口：

1. eval gate 增加 suite-level hint recovery 阈值。
2. comparison report 增加 hint recovery regression 检查。
3. run manifest 写入 summary，便于外部 dashboard 使用。
4. hint recovery 按 tool name/schema path/schema keyword 拆分。
5. real 9B/flash eval suite 增加 hint recovery tasks。

## 最新进展：Iteration 068

本轮把 schema repair hint recovery summary 接入 release gate。

已完成：

1. `evaluate_eval_run_gate` 新增：
   - `min_schema_repair_hint_recovery_rate`
   - `max_schema_repair_hint_failures`
2. Gate aggregates 新增：
   - `schema_repair_hints_seen`
   - `schema_repair_hint_successes`
   - `schema_repair_hint_failures`
   - `schema_repair_hint_recovery_rate`
3. Gate 优先读取 `eval-report.json` 的顶层 `summary`，旧报告缺 summary 时回退扫描 result-level metrics。
4. CLI `metis eval gate` 新增：
   - `--min-schema-repair-hint-recovery-rate`
   - `--max-schema-repair-hint-failures`
5. Gate markdown/json 会输出新增 aggregates 和 thresholds。

新增验证：

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py -q`：43 passed
- `python -m compileall -q metis`：通过

新的任务缺口：

1. run manifest 写入 summary。
2. comparison report 增加 hint recovery regression 检查。
3. real small-model eval suite 增加 hint recovery tasks。
4. gate 支持按 hint type 的阈值。

## 最新进展：Iteration 069

本轮把 eval suite summary 写入 run manifest 和 latest pointer。

已完成：

1. generic eval `manifest.json` 新增 `summary`。
2. generic eval `latest.json` 新增 `summary`。
3. real small-model eval `manifest.json` 新增 `summary`。
4. real small-model eval `latest.json` 新增 `summary`。
5. 四处均复用 `EvalSuiteResult.summary`，避免指标计算分叉。

新增验证：

- `python -m pytest tests\unit\test_eval_suite_run.py tests\e2e\test_local_9b_eval.py -q`：13 passed, 3 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. comparison report 增加 summary delta。
2. comparison report 增加 hint recovery regression。
3. manifest schema version 需要显式定义。
4. real small-model eval suite 增加 hint recovery tasks。

## 最新进展：Iteration 070

本轮把 run-level summary 接入 eval run comparison。目标是让 Metis 不只知道“单次运行是否达标”，还要知道“新版本是否让小模型的 schema repair hint recovery 退化”。

已完成：

1. `compare_eval_runs` 新增 `summary_diff`。
2. `comparison.json` 输出：
   - `schema_repair_hint_recovery_rate`
   - `schema_repair_hint_failures`
   - `schema_repair_hint_type_failure_deltas`
   - `schema_repair_hint_type_failure_increases`
3. `comparison.md` 新增 `## Summary Drift`，直接展示 recovery rate、hint failure count 和 hint type failure increase。
4. release/strict profile 新增 regression reason：
   - `schema_repair_hint_recovery_rate_decreased`
   - `schema_repair_hint_failures_increased`
   - `schema_repair_hint_type_failures_increased`
5. regression reason links 现在会携带并展示 summary change payload，避免 Markdown 只显示 `recorded`。
6. 推荐修复动作新增 hint recovery 相关说明。

新增验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：30 passed
- `python -m compileall -q metis`：通过

新的任务缺口：

1. real small-model eval suite 增加 hint recovery 专项任务。
2. comparison report 增加 hint type success/failure 完整表。
3. comparison profile 支持按 hint type 设置阈值。
4. manifest/latest/eval report 增加 schema version。
5. trace timeline 增加独立 `schema.repair_hint` event，便于回放和 dashboard 展示。

## 最新进展：Iteration 071

本轮把 schema repair hint 写入 runtime trace timeline，形成独立的 `schema.repair_hint` event。

已完成：

1. `AgentLoop` 在带 `schema_repair_hints` 的 schema failure 后额外记录 `schema.repair_hint`。
2. event 保留：
   - `parent_event_id`
   - `schema_errors`
   - `schema_repair_hints`
   - `schema_repair_hint_types`
   - `schema_repair_hint_details`
   - `hint_count`
3. event 绑定 `tool_name` 和 `tool_call_id`，方便从 hint 回溯到具体失败工具调用。
4. timeline Markdown 能直接显示 hint type summary。
5. 运行时仍保留 `tool.result` metadata，避免破坏既有 eval metrics 和 failure artifact。

新增验证：

- `python -m pytest tests\integration\test_agent_loop_schema_guard.py tests\unit\test_timeline.py -q`：16 passed
- `python -m compileall -q metis`：通过

新的任务缺口：

1. repair task 生成器优先锚定 `schema.repair_hint` event id。
2. comparison reason links 增加 timeline event id 级别链接。
3. failure diagnosis 增加 schema repair hint event 摘要。
4. real small-model eval suite 增加 hint recovery trace 任务。
5. trace dashboard 增加 schema repair hint 分组视图。

## 最新进展：Iteration 072

本轮把 `schema.repair_hint` 接入 repair task 的 critical event 选择。

已完成：

1. `select_critical_event()` 新增 schema repair hint 优先级。
2. 当 timeline 同时包含 failed `tool.result` 和 `schema.repair_hint` 时，critical event 选择 hint event。
3. finalization 失败仍然优先级最高，避免把最终交付校验错误误判成 schema hint 错误。
4. `build_repair_tasks_from_diagnosis()` 无需改变输出结构，但 `critical_event_ids` 现在可以指向 `schema.repair_hint`。
5. repair task 仍保留完整 `timeline_event_ids`，便于从 hint event 回溯到 parent tool result。

新增验证：

- `python -m pytest tests\unit\test_timeline.py tests\unit\test_eval_compare.py -q`：38 passed
- `python -m compileall -q metis`：通过

新的任务缺口：

1. failure diagnosis 增加 schema repair hint event 摘要。
2. targeted eval stub 从 hint event payload 中生成更具体的 schema repair 任务。
3. comparison reason links 增加 event-level references。
4. repair plan 按 hint type 聚合 schema 类修复任务。

## 最新进展：Iteration 073

本轮把 `schema.repair_hint` event 摘要接入 comparison diagnosis。

已完成：

1. `eval_run_comparison_diagnosis()` 新增 `schema_repair_hint_events`。
2. diagnosis 会按 task id 汇总：
   - `event_id`
   - `parent_event_id`
   - `tool_name`
   - `tool_call_id`
   - `schema_errors`
   - `hint_types`
   - `hints`
   - `hint_details`
3. `eval_run_diagnosis_to_markdown()` 展示 hint event 摘要。
4. `build_repair_tasks_from_diagnosis()` 保留 `schema_repair_hint_events`，供后续 targeted eval stub 使用。
5. 新增测试覆盖 diagnosis 读取 timeline、Markdown 展示、repair task 继承。

新增验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：32 passed
- `python -m compileall -q metis`：通过

新的任务缺口：

1. targeted eval stub 从 `schema_repair_hint_events` 生成具体 schema repair eval skeleton。
2. repair plan 按 hint type 聚合 schema repair 任务。
3. comparison reason links 增加 event-level references。
4. real small-model eval suite 增加 hint diagnosis trace 任务。

## 最新进展：Iteration 074

本轮把 `schema_repair_hint_events` 接入 targeted eval stub 生成。

已完成：

1. `build_eval_stubs_from_repair_tasks()` 会从 hint events 中提取：
   - `schema_repair_hint_types`
   - `schema_repair_hint_paths`
   - `schema_repair_hint_keywords`
2. targeted eval stub 保留原始 `schema_repair_hint_events`。
3. schema hint 相关 prompt 会包含 hint type、schema path、schema keyword。
4. schema hint 相关 constraints 自动增加：
   - `min_schema_repair_hint_successes=1`
   - `max_schema_repair_hint_failures=0`
5. `suggested_assertion` 会指向具体 hint type recovery。
6. materialized targeted eval suite 保留 hint event payload 和 hint types。

新增验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：33 passed
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 从 `schema_repair_hint_details` 推断 malformed/corrected 参数模板。
2. 为 `add_required_property`、`remove_additional_property`、`increase_array_items` 建第一批模板。
3. materialized eval suite 增加 hint-aware task spec metadata。
4. real small-model eval suite 增加由 hint-aware stub 转化来的真实任务。

## 最新进展：Iteration 075

本轮从 `schema_repair_hint_details` 推断 malformed/corrected argument templates。

已完成：

1. targeted eval stub 新增 `schema_repair_argument_templates`。
2. 每个模板包含：
   - `hint_type`
   - `schema_path`
   - `schema_keyword`
   - `malformed_arguments`
   - `corrected_arguments`
   - `notes`
3. 第一批覆盖：
   - `add_required_property`
   - `remove_additional_property`
   - `increase_array_items`
   - `reduce_array_items`
   - `fix_type`
   - `increase_numeric_value`
   - `reduce_numeric_value`
   - `fix_string_pattern`
   - `use_enum_value`
4. Markdown stub 和 materialized suite 都保留模板。
5. 新增测试覆盖 required/additionalProperties/minItems 三类模板。

新增验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：33 passed
- `python -m compileall -q metis`：通过

新的任务缺口：

1. argument template 增加 `tool_name`。
2. 从 tool schema 推断占位符类型。
3. 把 corrected template 转成 `required_tool_arguments`。
4. materialized suite 输出 hint-aware metadata 到 task spec。

## 最新进展：Iteration 076

本轮把 schema repair argument template 转成 `required_tool_arguments`。

已完成：

1. `schema_repair_argument_templates` 新增 `tool_name`。
2. `build_eval_stubs_from_repair_tasks()` 会从 corrected template 生成 `required_tool_arguments`。
3. 生成规则保持保守：
   - 没有 `tool_name` 不生成；
   - `corrected_arguments` 为空不生成；
   - 占位符用 `contains` 谓词表达，不伪装成真实业务值。
4. materialized targeted suite 保留这些 required tool argument gates。
5. 新增测试验证写盘后的 suite 可以通过 schema-aware validation。

新增验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：34 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`：90 passed
- `python -m pytest -q`：312 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 从 tool schema 推断 placeholder 类型和值。
2. 生成 prompt 时包含 malformed/corrected 参数对。
3. materialized suite 增加 schema version。
4. real small-model eval suite 增加由 hint template 生成的任务。

## 最新进展：Iteration 077

本轮把 schema repair argument template 的宽泛占位符升级为 schema-compatible placeholder。

已完成：

1. targeted eval stub 会从 `schema_repair_hint_events` 提取 `tool_name`，并把 hint 里出现的工具加入 `allowed_tools`。
2. placeholder 生成器会读取内置工具 schema：
   - 通过 `ToolRegistry` 创建 registry；
   - 通过 `register_builtin_tools()` 注册内置工具；
   - 通过 `tool_name + schema_path leaf` 找到字段 schema。
3. corrected template 会生成更具体的 schema-compatible 值：
   - `write_file.path` -> `outputs/metis-placeholder.txt`
   - `run_command.command` 空数组修复 -> `["metis-placeholder-command_item"]`
   - enum、number、boolean、array、oneOf 均有保守生成策略。
4. `required_tool_arguments` 会从 schema-compatible corrected template 派生。
5. 写盘后的 materialized suite 继续通过 schema-aware validation。

新增验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：34 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`：90 passed
- `python -m pytest -q`：312 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 把 malformed/corrected 参数对注入 targeted eval prompt，让真实模型运行时能看到明确修复目标。
2. 支持 suite-local/custom tool schema，而不只依赖内置工具 schema。
3. 为 materialized targeted suite 增加 schema version。
4. 按 hint type 改进 `oneOf` 分支选择，而不是始终偏向 array 分支。
5. 把 hint-derived materialized tasks 接入真实 9B provider eval。

## 最新进展：Iteration 078

本轮把 schema repair argument template 注入 targeted eval prompt。

已完成：

1. `_eval_stub_for_repair_task()` 会把生成好的 `argument_templates` 传给 `_eval_stub_prompt()`。
2. `_eval_stub_prompt()` 新增 prompt-visible schema repair argument context。
3. 每个模板会以确定性 JSON 片段写入 prompt，包含：
   - `tool`
   - `hint_type`
   - `schema_path`
   - `malformed_arguments`
   - `corrected_arguments`
4. prompt 明确说明这些模板是 failure-shape target，并说明 placeholder 是 schema-compatible template，不是业务数据。
5. 测试覆盖了 `write_file.path`、unsupported `url` 和 `run_command.command` 的 prompt 注入。

新增验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：34 passed
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 为 materialized targeted suite 增加 schema version。
2. prompt 中的 argument template context 需要数量限制、排序策略和溢出摘要。
3. 支持 suite-local/custom tool schema。
4. 增加 eval runner 对 malformed/corrected template 的专用 metrics。
5. 把 hint-derived tasks 接入真实 9B provider eval。

## 最新进展：Iteration 079

本轮为 materialized targeted suite 增加 schema version。

已完成：

1. 新增 `MATERIALIZED_TARGETED_EVAL_SUITE_SCHEMA_VERSION = "1"`。
2. `materialize_eval_suite_from_stubs()` 生成的 suite 顶层写入 `schema_version: "1"`。
3. `eval_suite_to_markdown()` 会展示 schema version。
4. 测试确认：
   - 内存 suite 带版本；
   - Markdown 带版本；
   - 写盘后的 `targeted-eval-suite.json` 保留版本。

新增验证：

- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`：54 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`：90 passed
- `python -m pytest -q`：312 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. validator 需要支持 known schema version 检查，而不是只检查字符串类型。
2. runner 需要 version-aware load path，为后续 migration 留接口。
3. 需要新增 suite schema 文档，记录 version 1 的字段语义。
4. prompt argument template context 需要数量限制、排序策略和溢出摘要。
5. 支持 suite-local/custom tool schema。

## 最新进展：Iteration 080

本轮把 eval suite validator 从“版本字段类型检查”升级为“supported schema version 检查”。

已完成：

1. `suite_validation.py` 新增 `SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS = frozenset({"1"})`。
2. `_validate_top_level()` 增加版本支持校验：
   - 缺失版本：warning，保持旧 suite 兼容；
   - 非字符串版本：error；
   - 未支持字符串版本：error。
3. validation report 新增 `supported_schema_versions`。
4. Markdown validation report 展示 supported schema versions。
5. 新增测试确认 `schema_version: "2"` 会被拒绝。

新增验证：

- `python -m pytest tests\unit\test_eval_suite_validation.py -q`：13 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`：91 passed
- `python -m pytest -q`：313 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 新增 `docs/evals/suite-schema.md`，记录 schema version 1 的字段语义。
2. runner 增加 version-aware load path，为 migration 留接口。
3. prompt argument template context 需要数量限制、排序策略和溢出摘要。
4. 支持 suite-local/custom tool schema。
5. release gate 需要定义 unversioned suite 策略。

## 最新进展：Iteration 081

本轮新增 eval suite schema version 1 的正式文档。

已完成：

1. 新增 `docs/evals/suite-schema.md`。
2. 文档覆盖：
   - suite schema purpose；
   - supported versions；
   - top-level fields；
   - wrapped task entry；
   - direct `EvalTaskSpec` entry；
   - `EvalTaskSpec` fields；
   - `required_tool_arguments`；
   - schema repair metadata；
   - compatibility rules；
   - migration rules；
   - release gate expectations。
3. `tests/unit/test_docs_exist.py` 新增文档契约测试，检查 suite schema 文档包含关键治理内容。

新增验证：

- `python -m pytest tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_compare.py -q`：49 passed
- `python -m pytest tests\unit\test_docs_exist.py tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`：93 passed
- `python -m pytest -q`：314 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. runner 增加 version-aware load path。
2. 生成 machine-readable suite schema 或 schema snapshot。
3. prompt argument template context 需要数量限制、排序策略和溢出摘要。
4. 支持 suite-local/custom tool schema。
5. release gate 增加 unversioned suite 策略。

## 最新进展：Iteration 082

本轮把 runner 的 eval suite 加载路径升级为 version-aware。

已完成：

1. `metis.evals.runner` 新增 `SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS = frozenset({"1"})`。
2. 新增 `normalize_eval_suite_payload()`：
   - 支持 legacy list payload；
   - 拒绝非 object/list payload；
   - 保持 unversioned suite 兼容；
   - 拒绝非字符串版本；
   - 拒绝 unsupported schema version。
3. 新增 `load_versioned_eval_suite_payload()`。
4. `load_eval_task_specs()` 改为走 version-aware loader。
5. `suite_run.load_eval_suite_payload()` 改为复用同一个 loader。
6. `suite_validation.py` 复用 runner 层 supported version set，避免 validator/runner 分叉。
7. 新增测试覆盖 runner 和 suite_run 对 `schema_version: "2"` 的拒绝。

新增验证：

- `python -m pytest tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py -q`：59 passed
- `python -m pytest tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py -q`：129 passed
- `python -m pytest -q`：316 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 生成 machine-readable suite schema 或 schema snapshot。
2. prompt argument template context 需要数量限制、排序策略和溢出摘要。
3. 支持 suite-local/custom tool schema。
4. release gate 增加 unversioned suite 策略。
5. suite version/migration 增加专用异常与诊断码。

## 最新进展：Iteration 083

本轮新增机器可读的 eval suite schema snapshot。

已完成：

1. 新增 `docs/evals/suite-schema-v1.json`。
2. JSON schema snapshot 覆盖：
   - top-level suite object；
   - `schema_version` const `1`；
   - `tasks` array；
   - wrapped task entry；
   - direct `EvalTaskSpec` entry；
   - `required_tool_arguments`；
   - list/bool/int/dict task spec fields；
   - non-negative nullable counters；
   - `x-metis` metadata。
3. `docs/evals/suite-schema.md` 增加 machine-readable snapshot 链接。
4. `tests/unit/test_docs_exist.py` 新增契约测试，从代码字段集合反查 JSON snapshot，降低文档/validator/runner 漂移风险。

新增验证：

- `python -m pytest tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py -q`：16 passed
- `python -m pytest tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_compare.py -q`：96 passed
- `python -m pytest -q`：317 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. prompt argument template context 需要数量限制、排序策略和溢出摘要。
2. 支持 suite-local/custom tool schema。
3. release gate 增加 unversioned suite 策略。
4. suite version/migration 增加专用异常与诊断码。
5. validation report 增加 suite schema snapshot id/hash。

## 最新进展：Iteration 084

本轮为 prompt-visible schema repair argument templates 增加数量上限、稳定排序和溢出摘要。

已完成：

1. 新增 `MAX_PROMPT_SCHEMA_REPAIR_ARGUMENT_TEMPLATES = 5`。
2. `_eval_stub_argument_template_context()` 现在只把前 5 个模板完整写入 prompt。
3. prompt 会写入 `showing N of M templates`。
4. 如果模板被省略，prompt 会写入 omitted 数量和 `hint_type@schema_path` 摘要。
5. 新增 `_prompt_argument_template_sort_key()`：
   - 有 corrected arguments 的模板优先；
   - 再按 tool、path、hint type、keyword 稳定排序。
6. 新增测试覆盖 7 个模板时的截断、排序和 omitted 摘要。

新增验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：35 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py -q`：130 passed
- `python -m pytest -q`：318 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 支持 suite-local/custom tool schema。
2. release gate 增加 unversioned suite 策略。
3. validation report 增加 suite schema snapshot id/hash。
4. suite version/migration 增加专用异常与诊断码。
5. prompt context 增加 profile-aware budget。

## 最新进展：Iteration 085

本轮把 schema repair placeholder 生成扩展到 custom tool schemas。

已完成：

1. repair task 顶层支持 `tool_schemas`。
2. schema repair hint event 支持 `tool_schema` 和 `parameters`。
3. schema resolution 优先级：
   - event-level schema；
   - task-level `tool_schemas[tool_name]`；
   - builtin tool schema；
   - fallback placeholder heuristics。
4. `build_eval_stubs_from_repair_tasks()` 输出的 stub 保留 `tool_schemas`。
5. 新增测试覆盖：
   - custom integer minimum placeholder；
   - custom enum placeholder；
   - required tool arguments 派生；
   - event-level schema 覆盖 task-level schema。

新增验证：

- `python -m pytest tests\unit\test_eval_compare.py -q`：37 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py -q`：132 passed
- `python -m pytest -q`：320 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. materialized suite 保留 task/stub `tool_schemas`。
2. suite schema v1 文档和 JSON snapshot 增加 `tool_schemas`。
3. validation report 增加 suite schema snapshot id/hash。
4. release gate 增加 unversioned suite 策略。
5. custom tool schema 接入 generic eval validation context。

## 最新进展：Iteration 086

本轮让 materialized targeted suite 保留 custom `tool_schemas`，并同步更新 suite schema contract。

已完成：

1. `materialize_eval_suite_from_stubs()` 的 task wrapper 保留 `tool_schemas`。
2. `docs/evals/suite-schema.md` 的 wrapped task entry 文档增加 `tool_schemas`。
3. `docs/evals/suite-schema-v1.json` 的 `wrapped_task_entry.properties` 增加 `tool_schemas`。
4. 文档契约测试确认 JSON snapshot 中存在 `tool_schemas`。
5. eval compare 测试确认 custom schema 从 stub 写入 materialized suite task wrapper。

新增验证：

- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_docs_exist.py -q`：40 passed
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py -q`：99 passed
- `python -m pytest -q`：320 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. custom tool schema 接入 generic eval validation context。
2. validation report 增加 suite schema snapshot id/hash。
3. release gate 增加 unversioned suite 策略。
4. suite version/migration 增加专用异常与诊断码。
5. suite-level `tool_schemas` 设计。

## 最新进展：Iteration 087

本轮让 suite-local custom `tool_schemas` 自动参与 eval suite validation。

已完成：

1. `validate_eval_suite()` 构造 merged tool schema view。
2. schema 合并优先级：
   - suite-local `tool_schemas`；
   - explicit `tool_schemas` 覆盖。
3. 如果没有显式 `available_tools`，validator 会用 merged tool schema keys 作为 tool inventory。
4. 新增 `_suite_local_tool_schemas()` 从 wrapped task entries 提取 custom schemas。
5. 新增 `_merged_tool_schemas()` 统一合并逻辑。
6. 新增测试覆盖：
   - suite-local custom schema 校验通过；
   - suite-local schema 检出参数类型错误；
   - explicit schema 覆盖 suite-local schema。

新增验证：

- `python -m pytest tests\unit\test_eval_suite_validation.py -q`：16 passed
- `python -m pytest tests\unit\test_eval_suite_validation.py tests\unit\test_eval_compare.py tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_cli_eval.py -q`：135 passed
- `python -m pytest -q`：323 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. validation report 增加 suite schema snapshot id/hash。
2. release gate 增加 unversioned suite 策略。
3. suite version/migration 增加专用异常与诊断码。
4. suite-level `tool_schemas` 设计。
5. suite-local tool schema 合法性检查。

## 最新进展：Iteration 088

本轮把 suite schema snapshot metadata 写入 eval suite validation report。

已完成：

1. `suite_validation.py` 新增 `SUITE_SCHEMA_SNAPSHOT_PATH`。
2. 新增 `_suite_schema_snapshot_metadata()`。
3. validation JSON report 现在包含：
   - `suite_schema_id`
   - `suite_schema_path`
   - `suite_schema_sha256`
4. validation Markdown report 展示 schema id、path 和 sha256。
5. 测试确认 report 的 hash 等于当前 `docs/evals/suite-schema-v1.json` 文件 SHA256。

新增验证：

- `python -m pytest tests\unit\test_eval_suite_validation.py -q`：16 passed
- `python -m pytest tests\unit\test_eval_suite_validation.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_runner.py tests\unit\test_eval_compare.py -q`：135 passed
- `python -m pytest -q`：323 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. release gate 增加 unversioned suite 策略。
2. suite version/migration 增加专用异常与诊断码。
3. suite-level `tool_schemas` 设计。
4. suite-local tool schema 合法性检查。
5. generic eval run manifest 记录 suite schema snapshot metadata。

## 最新进展：Iteration 089

本轮让 `metis eval run-suite --gate` 拒绝 unversioned suite。

已完成：

1. `_eval_run_suite()` 在 provider 环境检查之前增加 release gate suite-version check。
2. 新增 `_validation_has_unversioned_suite()`。
3. 判定 unversioned suite 的方式：
   - validation report 的 `schema_version` 为 `unversioned`；或
   - warnings 中存在 `schema_version/missing`。
4. 命中策略时：
   - 打印 validation markdown；
   - 打印明确失败原因；
   - 返回 exit code `1`；
   - 不检查 env；
   - 不运行模型。
5. 新增 CLI 测试覆盖 `run-suite --gate` 拒绝 unversioned suite。

新增验证：

- `python -m pytest tests\unit\test_cli_eval.py -q`：37 passed
- `python -m pytest tests\unit\test_cli_eval.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_runner.py tests\unit\test_eval_compare.py -q`：136 passed
- `python -m pytest -q`：324 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. generic eval run manifest 记录 suite schema snapshot metadata。
2. suite version/migration 增加专用异常与诊断码。
3. suite-level `tool_schemas` 设计。
4. suite-local tool schema 合法性检查。
5. 独立 `metis eval gate --run` 增加 suite schema evidence 检查。

## 最新进展：Iteration 090

本轮让 generic eval run artifacts 记录 suite schema snapshot metadata。

已完成：

1. `suite_validation.py` 导出 `suite_schema_snapshot_metadata()`。
2. `generic_eval_suite_metadata()` 写入：
   - `suite_schema_id`
   - `suite_schema_path`
   - `suite_schema_sha256`
3. `generic_eval_suite_manifest()` 顶层写入 schema id/path/hash。
4. `write_generic_eval_latest_pointer()` 写入 schema id/hash。
5. 测试确认 metadata hash 等于当前 `docs/evals/suite-schema-v1.json` 的真实 SHA256。

新增验证：

- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py -q`：25 passed
- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py tests\unit\test_eval_runner.py -q`：136 passed
- `python -m pytest -q`：324 passed, 4 skipped
- `python -m compileall -q metis`：通过

新的任务缺口：

1. 独立 `metis eval gate --run` 增加 suite schema evidence 检查。
2. real-small-model manifest 增加 schema metadata 或声明非-loadable-suite。
3. suite version/migration 增加专用异常与诊断码。
4. suite-level `tool_schemas` 设计。
5. suite-local tool schema 合法性检查。

## 1. 当前定位

Metis 的目标不是做某一个业务智能体，而是成为跨场景智能体开发的 harness 底座。它应该让后续的业务智能体只关注领域知识、工具接入、交付物标准和业务流程，而不用重复建设运行循环、工具治理、状态管理、证据体系、评测体系、恢复机制、审计机制和部署控制面。

面向 9B 或 flash 级小模型时，harness 必须承担更多工程责任：

1. 把复杂任务拆成稳定的小步。
2. 把工具调用约束变成可执行 schema。
3. 把模型错误变成可恢复反馈。
4. 把“完成了”的口头声明变成可核验证据。
5. 把质量要求变成可运行 gate。
6. 把多智能体协作变成可审计流程，而不是简单并发聊天。
7. 把每一次失败都沉淀为 eval 指标和改进任务。

## 2. 当前基线

本轮验证结果：

- 全量测试：`160 passed, 2 skipped`
- 编译检查：`python -m compileall -q metis` 通过
- 最新新增能力：schema-invalid 工具调用的结构化修复反馈与 eval repair metrics

已具备的主要能力：

- `AgentLoop`
- `RuntimeStatus`
- `StrictOutputParser`
- `FinalizationGuard`
- `ToolRegistry`
- `ToolDispatcher`
- `ToolPolicyEngine`
- `ToolArgumentSchemaValidator`
- `EvidenceLedger`
- `EvidenceResolver`
- `ClaimEvidenceMatcher`
- `ToolEvidenceExtractor`
- `EvalRunner`
- 轨迹评测指标
- 工具顺序、必需工具、禁用工具、参数匹配评测
- schema violation 评测
- schema repair attempt/success/failure 评测

参考当前主流 agent harness 的设计趋势，OpenAI Agents SDK 文档强调 guardrails 应覆盖 input、output 和 tool invocation；尤其在有 handoff 或多角色流程时，tool guardrails 不能只放在最终输出层，而要围绕每次工具调用执行。Metis 当前的方向与这个结论一致：工具 schema、policy、pre-execution guard、finalization guard 必须形成多层防线。

## 3. 总体判断

Metis 已经从“能跑的 agent loop”进入“可治理 harness”的早期阶段，但离生产级通用底座还有明显距离。当前最重要的问题不是单点 bug，而是基础设施闭环还没有完全打通：

1. 真实小模型评测还不够强。
2. 工具错误恢复刚起步，还没有形成通用 repair protocol。
3. 证据体系仍偏初级，不能覆盖所有交付声明。
4. QualityGate 仍偏通用，缺少交付物类型专用 gate。
5. Swarm 仍是骨架，缺少生产级编排、隔离、合成和审核。
6. 场景模板与 agent scaffold 不完整。
7. 可观测性、审计、回放、部署控制面不足。
8. 文档和开发者体验还没有达到“拿来即用”的程度。

## 4. P0 问题拆解

### P0-01 真实 9B/flash E2E 评测不足

现状：

- `FakeProvider` 覆盖较多。
- 真实 API smoke 存在，但复杂任务不足。
- 不能证明小模型能稳定完成多步任务、工具调用、证据引用、质量门验证和最终交付。

风险：

- harness 看起来完整，但真实小模型可能卡在 parser、schema、上下文、工具顺序、错误恢复、final JSON 等细节。
- 没有真实失败分布，就无法决定下一步架构优化优先级。

任务：

1. 建立 `evals/real_model/` 任务集。
2. 接入 GLM flash/OpenAI-compatible provider 的真实运行配置。
3. 设计 20 个跨场景最小任务：
   - 文件读取总结
   - 文件生成
   - 命令执行
   - 测试运行
   - 证据引用
   - schema 错误修复
   - 多步交付
   - 质量门失败后修复
   - 上下文压缩
   - 禁止工具绕过
4. 每个任务记录：
   - success
   - final_verified
   - turns_used
   - parser_failures
   - schema_violations
   - schema_repair_successes
   - invalid_tool_calls
   - policy_blocks
   - evidence_resolution_failures
   - false_completion
5. 生成 markdown/json/html 三种报告。
6. 设定真实模型准入线：
   - 基础任务成功率
   - 工具任务成功率
   - 证据任务成功率
   - 修复任务成功率
   - final_verified 比例

验收：

- 至少 20 个真实模型 eval task。
- 报告可复现。
- 失败样本能映射到明确 failure category。

### P0-02 通用 Tool Repair Protocol 不完整

现状：

- schema-invalid 已经能被 dispatcher 阻断。
- AgentLoop 已能给模型返回结构化 repair feedback。
- EvalRunner 已能统计 repair attempt/success/failure。

缺口：

- 只覆盖 schema-invalid。
- 没有覆盖 unknown tool、not allowed、policy denied、command denied、tool runtime error、empty output、quality gate failed。
- 没有统一 error taxonomy。

任务：

1. 建立 `ToolFailureType`：
   - `unknown_tool`
   - `tool_not_allowed`
   - `schema_validation_failed`
   - `policy_denied`
   - `approval_required`
   - `runtime_error`
   - `timeout`
   - `empty_output`
   - `unsafe_command`
2. 所有 ToolResult blocked/error 都必须带：
   - `failure_type`
   - `recoverable`
   - `repair_instruction`
   - `retry_allowed`
   - `retry_budget_key`
3. AgentLoop 根据 failure_type 生成一致的 tool feedback。
4. 增加 retry budget：
   - per tool
   - per failure type
   - per turn
   - per run
5. EvalRunner 增加：
   - repair_attempts_by_type
   - repair_successes_by_type
   - unrecovered_failures_by_type
6. 对危险失败设置不可恢复：
   - policy denied 不允许模型绕过。
   - approval required 必须进入 HITL。
   - unsafe command 只能改用安全工具或终止。

验收：

- 每种失败类型都有单元测试。
- 至少 5 种失败类型有集成恢复测试。
- eval 报告能区分“模型能力问题”和“权限/安全问题”。

### P0-03 证据体系仍不够强

现状：

- EvidenceLedger 能记录证据。
- EvidenceResolver 能检查 final evidence refs。
- ClaimEvidenceMatcher 已开始防止虚假完成。

缺口：

- claim 类型仍不完整。
- evidence strength 还不够系统。
- 不同交付声明缺少强证据规则。

任务：

1. 建立 `ClaimType`：
   - file_created
   - file_modified
   - command_executed
   - tests_passed
   - api_called
   - uploaded
   - downloaded
   - reviewed
   - rendered
   - screenshot_verified
   - cited_source
2. 建立 `EvidenceStrength`：
   - weak
   - medium
   - strong
3. 建立 claim 到 evidence 的强规则：
   - “测试已通过”必须有 test evidence，且 exit_code=0。
   - “文件已生成”必须有 artifact/file evidence，且路径存在。
   - “GitHub 已上传”必须有 remote URL、commit SHA 或 GitHub API 结果。
   - “截图已验证”必须有 screenshot/render evidence。
4. 增加 evidence extractor：
   - TestEvidenceExtractor
   - GitEvidenceExtractor
   - FileEvidenceExtractor
   - WebEvidenceExtractor
   - RenderEvidenceExtractor
5. finalization 不再只检查 evidence_refs 是否存在，还要检查 claim/evidence 类型匹配。

验收：

- 虚假完成测试覆盖所有常见 claim。
- final JSON 引用错误 evidence type 会被 blocked。

### P0-04 QualityGate 类型不够丰富

现状：

- 已有基础 gate。
- 对 markdown/code/test/git/render 等交付物仍缺少专用 gate。

任务：

1. `MarkdownReportGate`
   - 标题结构
   - 空洞段落
   - TODO/placeholder
   - 引用完整性
   - 表格完整性
2. `CodeChangeGate`
   - diff 存在
   - 测试覆盖
   - lint/compile
   - public API 变化说明
3. `TestRunGate`
   - exit code
   - fail count
   - skipped count
   - command provenance
4. `GitUploadGate`
   - repo URL
   - branch
   - commit SHA
   - remote push evidence
5. `RenderGate`
   - PDF/PPT/image 是否可打开
   - 页面是否空白
   - 关键文本是否存在
6. `CitationGate`
   - 每条外部事实有来源
   - 来源 URL 可访问
   - 引用不超版权限制

验收：

- 每种 gate 至少 3 个通过/失败样例。
- EvalRunner 可以按任务声明 quality_gates。

### P0-05 Agent Definition 与 Scaffold 缺失

现状：

- Metis 有 runtime 组件，但还没有真正的“新建一个场景 agent”的标准入口。

任务：

1. 设计 `agent.yaml`：
   - name
   - description
   - model_profile
   - tools
   - skills
   - adapters
   - quality_gates
   - evidence_policy
   - eval_suite
   - workspace_policy
2. CLI scaffold：
   - `metis init agent <name>`
   - `metis add tool`
   - `metis add eval`
   - `metis run`
   - `metis eval`
3. 生成目录：
   - `agents/<name>/agent.yaml`
   - `agents/<name>/instructions.md`
   - `agents/<name>/tools/`
   - `agents/<name>/evals/`
   - `agents/<name>/quality/`
4. 提供模板：
   - research-agent
   - coding-agent
   - document-agent
   - data-agent
   - business-plan-agent

验收：

- 一个新场景 agent 能在 5 分钟内 scaffold 并跑通 smoke eval。

### P0-06 Swarm 仍是骨架

现状：

- 有 swarm 基础结构。
- 还没有生产级角色隔离、审计合成、冲突解决和 reviewer team。

任务：

1. 定义角色模型：
   - planner
   - executor
   - researcher
   - reviewer
   - verifier
   - integrator
2. 每个角色有：
   - tool scope
   - context scope
   - output schema
   - evidence requirement
3. 增加 reviewer team：
   - anti-fabrication reviewer
   - test reviewer
   - security reviewer
   - delivery reviewer
4. 增加合成器：
   - merge findings
   - resolve conflicts
   - require evidence
   - generate final plan
5. 增加 swarm eval：
   - 单 agent vs swarm 成功率对比
   - token/turn/latency 对比
   - reviewer catch rate

验收：

- swarm 能完成一个复杂文档/代码任务。
- reviewer 能拦截至少 3 类虚假完成。

### P0-07 可观测性与回放不足

现状：

- 有 HookBus。
- 缺少统一 trace schema、run timeline、失败回放工具。

任务：

1. 定义 `TraceEvent`：
   - run_started
   - model_called
   - model_returned
   - tool_called
   - tool_blocked
   - tool_succeeded
   - evidence_recorded
   - quality_gate_run
   - finalization_checked
   - run_finished
2. 保存 run timeline。
3. 提供 `metis trace show <run_id>`。
4. 提供 `metis trace replay <run_id>`。
5. eval report 链接 trace。

验收：

- 任意失败 eval 能打开完整 timeline。
- 可定位失败发生在 parser、tool、policy、evidence、quality 还是 finalization。

## 5. P1 问题拆解

### P1-01 ContextEngine 需要更适合小模型

任务：

1. 按消息类型分层预算。
2. 保留最近失败反馈。
3. 保留当前 plan/step。
4. 保留证据摘要。
5. 压缩长工具输出。
6. 对小模型提供短 schema，而不是完整冗长 schema。
7. 增加上下文污染测试。

### P1-02 Provider Adapter 需要生产化

任务：

1. OpenAI-compatible provider 支持：
   - retry
   - timeout
   - rate limit
   - streaming accumulation
   - raw response persistence
2. GLM provider profile：
   - model name
   - thinking config
   - max tokens
   - temperature
   - stream
3. provider health check。
4. provider failure eval。

### P1-03 Tool Registry 需要包管理语义

任务：

1. tool namespace。
2. tool version。
3. tool dependency。
4. tool capability tags。
5. tool risk metadata。
6. adapter 自动注册工具。
7. tool docs generation。

### P1-04 状态机需要更细

任务：

1. RunState：
   - created
   - planning
   - executing
   - verifying
   - repairing
   - finalizing
   - blocked
   - failed
   - final
2. StepState：
   - pending
   - running
   - waiting_tool
   - waiting_approval
   - verifying
   - needs_repair
   - done
   - failed
3. 每次状态变化写 trace。

### P1-05 安全和权限边界还要加强

任务：

1. workspace allowlist。
2. file write policy。
3. shell command structured execution。
4. network tool permission。
5. secret redaction。
6. external upload policy。
7. approval workflow。

## 6. P2 问题拆解

### P2-01 文档体系

任务：

1. Architecture overview。
2. Runtime guide。
3. Tool authoring guide。
4. Evidence policy guide。
5. Eval authoring guide。
6. Adapter guide。
7. Scenario scaffold tutorial。

### P2-02 示例项目

任务：

1. `examples/research_agent`
2. `examples/code_agent`
3. `examples/document_agent`
4. `examples/business_plan_agent`
5. 每个 example 都必须有 eval suite。

### P2-03 打包发布

任务：

1. pyproject metadata。
2. CLI entrypoint。
3. versioning。
4. release notes。
5. install smoke test。

## 7. 下一轮建议执行顺序

按“最短实现路径 + 最大可靠性收益”排序：

1. P0-02：通用 Tool Repair Protocol。
2. P0-01：真实 9B/flash eval suite。
3. P0-03：claim/evidence 强类型规则。
4. P0-04：QualityGate 专用化。
5. P0-05：agent.yaml + scaffold。
6. P0-07：trace timeline。
7. P0-06：生产级 swarm。

理由：

- Tool repair 直接提升小模型可用性。
- 真实 eval 决定所有优化是否有效。
- 证据与质量门决定可信交付。
- scaffold 决定跨场景复用效率。
- trace 决定长期 debug 效率。
- swarm 应在单 agent harness 足够稳后增强，否则会放大不稳定性。

## 8. 当前已完成的本轮任务

Iteration 012 已完成：

1. schema-invalid 工具反馈结构化。
2. schema repair eval metrics。
3. recovered schema failure 显式评测开关。
4. 集成测试覆盖错参后修复。
5. 全量测试通过：`160 passed, 2 skipped`。

Iteration 013 已完成：

1. 新增 `ToolFailureType`。
2. 新增统一 `tool_failure_metadata()`。
3. Dispatcher 为以下失败类型附加结构化元数据：
   - unknown tool
   - tool not allowed
   - schema validation failed
   - policy denied
   - approval required
   - unsafe command
   - guardrail blocked
   - hook blocked
   - command failed
   - runtime error
4. AgentLoop 将所有带 `failure_type` 的工具失败转换成结构化反馈。
5. EvalRunner 新增 `tool_failure_types` 统计。
6. 定向测试通过：`38 passed`。
7. 全量测试通过：`163 passed, 2 skipped`。

Iteration 014 已完成：

1. EvalTaskSpec 新增通用工具修复门：
   - `min_tool_repair_successes`
   - `max_tool_repair_failures`
   - `allow_recovered_tool_failures`
2. EvalResult 新增通用工具修复指标：
   - `tool_repair_attempts`
   - `tool_repair_successes`
   - `tool_repair_failures`
   - `tool_repair_attempts_by_type`
   - `tool_repair_successes_by_type`
   - `tool_repair_failures_by_type`
3. recoverable tool failure 后续同工具成功调用会被计为 repair success。
4. unrecovered recoverable tool failure 会被计为 repair failure。
5. 全量测试通过：`165 passed, 2 skipped`。

Iteration 015 已完成：

1. ModelProfile 新增 `max_tool_repair_retries`。
2. small/small_strict/balanced/deep 分别设置不同 retry budget。
3. AgentLoop 按 tool name + failure type 统计 recoverable failure attempts。
4. 超出预算后，工具反馈会设置：
   - `retry_allowed=False`
   - `retry_budget_exhausted=True`
   - `repair_attempt_number`
   - `max_tool_repair_retries`
5. 新增集成测试覆盖 small profile 下重复 schema-invalid 的预算耗尽反馈。
6. 全量测试通过：`166 passed, 2 skipped`。

Iteration 016 已完成：

1. `ToolFailureType` 新增 `retry_budget_exhausted`。
2. AgentLoop 新增 failure lineage key：
   - tool name
   - canonicalized arguments
3. recoverable failure 超出 retry budget 后，lineage key 会被记录为 exhausted。
4. 后续同一工具同一参数指纹再次出现时，在 dispatcher 之前直接 blocked。
5. blocked result 包含：
   - `failure_type=retry_budget_exhausted`
   - `original_failure_type`
   - `retry_allowed=False`
   - `failure_lineage_key`
6. 新增集成测试证明第三次重复坏调用不会进入 handler。
7. 全量测试通过：`167 passed, 2 skipped`。

Iteration 017 已完成：

1. AgentLoop 新增 schema failure shape lineage。
2. 对 `schema_validation_failed`，shape key 使用：
   - tool name
   - failure type
   - schema_errors
3. schema failure 超出 retry budget 后，后续同一 schema 错误形态会在 dispatcher 前被 blocked。
4. 新增测试覆盖“content 改了但仍缺 path”的绕过尝试。
5. 全量测试通过：`168 passed, 2 skipped`。

Iteration 018 已完成：

1. Runtime error 新增 normalized exception shape：
   - exception_type
   - normalized error text
2. Command failure 新增 semantic command shape：
   - 忽略 flags
   - 数字归一为 `<value>`
   - 路径归一为 `<path>`
   - 使用前两个有效命令 token 形成语义形态
3. `failure_shape_key` 会进入结构化工具反馈。
4. command semantic shape 超出 retry budget 后，后续同语义命令会在 dispatcher 前被 blocked。
5. 新增测试覆盖 `python -m pytest tests/a.py/b.py/c.py` 这种轻微改路径绕过尝试。
6. 新增测试覆盖 runtime error 文本归一化。
7. 全量测试通过：`170 passed, 2 skipped`。

Iteration 019 已完成：

1. AgentLoop 的 pre-dispatch retry-budget block 增加 `pre_dispatch_block=True`。
2. EvalResult 新增：
   - `retry_budget_exhaustions`
   - `pre_dispatch_blocks`
   - `failure_shape_keys`
3. Eval markdown 报告新增 retry budget 和 pre-dispatch block 列。
4. 新增 EvalRunner 测试覆盖真实 AgentLoop 中 command semantic lineage 的报告统计。
5. 全量测试通过：`171 passed, 2 skipped`。

下一轮应为 lineage 指标增加 eval gates：

1. `max_retry_budget_exhaustions`
2. `max_pre_dispatch_blocks`
3. per-tool/per-shape threshold
4. required/forbidden failure shape keys

Iteration 020 已完成：

1. EvalTaskSpec 新增 lineage gates：
   - `max_retry_budget_exhaustions`
   - `max_pre_dispatch_blocks`
   - `required_failure_shape_keys`
   - `forbidden_failure_shape_keys`
   - `max_failure_shape_key_counts`
2. `_trajectory_errors()` 支持按 lineage 指标判定任务失败。
3. 新增测试覆盖 retry budget、pre-dispatch block、forbidden shape、shape count threshold。
4. 新增测试覆盖 required failure shape key 缺失。
5. 新增报告字段测试，确保 markdown 报告包含 retry budget 和 pre-dispatch block 列。
6. 全量测试通过：`173 passed, 2 skipped`。

下一轮应开始构建真实 9B/flash eval suite，把这些 gates 作为默认准入线，而不是只用 FakeProvider 验证框架逻辑。

Iteration 021 已完成：

1. 新增 `metis/evals/real_model_suite.py`。
2. 新增真实小模型 eval suite 入口：
   - `real_model_env_configured()`
   - `real_small_model_eval_tasks()`
   - `build_real_small_model_eval_runner()`
   - `run_real_small_model_eval_suite()`
3. 首批真实 provider eval tasks：
   - `strict-final-no-tools`
   - `read-then-summarize`
   - `safe-command`
4. 所有任务默认启用严格 gates：
   - `max_invalid_tool_calls=0`
   - `max_schema_violations=0`
   - `max_retry_budget_exhaustions=0`
   - `max_pre_dispatch_blocks=0`
5. 网络测试无真实 endpoint 配置时跳过，不伪造结果。
6. 更新 `docs/evals/9b-eval-report.md`。
7. 全量测试通过：`174 passed, 3 skipped`。

下一轮应把真实小模型 eval suite 从 3 个任务扩展到第一批 8-10 个任务，覆盖 schema repair、tool retry obedience、evidence finalization、safe command、forbidden tool 和 report generation。

Iteration 022 已完成：

1. 真实小模型 eval suite 从 3 个任务扩展到 9 个任务。
2. 新增任务覆盖：
   - write_file 报告生成
   - read_file -> write_file 顺序
   - forbidden shell/read-only 路径
   - schema repair for write_file
   - schema repair for run_command
   - run_test 安全命令
3. 普通任务默认零缺陷 gates：
   - `max_invalid_tool_calls=0`
   - `max_schema_violations=0`
   - `max_retry_budget_exhaustions=0`
   - `max_pre_dispatch_blocks=0`
4. repair 任务要求：
   - `min_schema_repair_successes=1`
   - `max_schema_repair_failures=0`
   - `allow_recovered_schema_failures=True`
5. 真实 runner 接入 `EvidenceLedger`，为后续 verified-final eval 做准备。
6. 更新 `docs/evals/9b-eval-report.md`。
7. 全量测试通过：`174 passed, 3 skipped`。

下一轮应补 verified-final/evidence-ref 真实任务，并让 real eval report 记录 model/base_url/profile 元数据。

Iteration 023 已完成：

1. AgentLoop 成功工具消息现在会把 evidence refs 回传给模型。
2. ToolResult metadata 新增 `evidence_refs`。
3. EvalSuiteResult 新增 `metadata`。
4. Eval JSON/Markdown 报告写入 metadata。
5. real small-model suite 新增 `real_small_model_eval_metadata()`。
6. real small-model suite 新增 `verified-test-evidence`。
7. `verified-test-evidence` 要求：
   - `required_evidence_sources=["test"]`
   - `require_verified_final=True`
8. 更新 `docs/evals/9b-eval-report.md`。
9. 全量测试通过：`176 passed, 3 skipped`。

下一轮应继续扩展 verified eval：

1. verified write_file/tool_output evidence；
2. verified read/write report evidence；
3. evidence ref 缺失/错误时的真实模型修复任务；
4. 将真实 eval 报告稳定写入 `docs/evals/` 的可版本化输出。

Iteration 024 已完成：

1. real small-model suite 新增 `verified-write-evidence`。
2. `verified-write-evidence` 要求：
   - `required_tools=["write_file"]`
   - `required_evidence_sources=["tool_output"]`
   - `require_verified_final=True`
   - `path=outputs/verified-write.md`
3. 新增集成测试证明 `write_file` 证据 ID 会回传给模型。
4. 更新 `docs/evals/9b-eval-report.md`。
5. 全量测试通过：`177 passed, 3 skipped`。

下一轮应补 verified read/write report evidence，并开始把真实 eval run report 稳定写入 `docs/evals/runs/`。

Iteration 025 已完成：

1. real small-model suite 新增 `verified-read-write-report-evidence`。
2. `verified-read-write-report-evidence` 要求：
   - `read_file` 读取 `README.md`
   - `write_file` 写入 `outputs/verified-read-write-report.md`
   - 工具顺序必须是 `read_file -> write_file`
   - final JSON 必须引用 `write_file` 返回的 `evidence_refs`
   - `required_evidence_sources=["tool_output"]`
   - `require_verified_final=True`
3. 新增稳定真实 eval 报告目录 helper：
   - `real_small_model_eval_report_dir()`
   - `write_real_small_model_eval_reports()`
   - `run_and_write_real_small_model_eval_suite()`
4. 默认真实 eval 报告目录为 `docs/evals/runs/latest/`。
5. 报告目录会写入：
   - `eval-report.json`
   - `eval-report.md`
6. 新增 e2e 测试覆盖：
   - 第 12 个真实 eval 任务声明
   - read/write 顺序门禁
   - required tool arguments
   - required evidence source
   - stable report writer 输出路径和 metadata
7. 定向测试通过：`3 passed, 3 skipped`。
8. 编译检查通过：`python -m compileall -q metis`。

下一轮应继续补真实 eval 的生产化操作面：

1. CLI：`metis eval real-small-model --run-name latest`。
2. timestamped run：`docs/evals/runs/YYYYMMDD-HHMMSS/`。
3. `latest` 指针策略：保留 latest 目录或写入 latest manifest。
4. eval run manifest：
   - run id
   - model
   - base url
   - profile
   - task count
   - started_at
   - completed_at
   - success_rate
5. failure-only markdown section，方便快速定位真实模型失败原因。
6. previous-run comparison，检测回归：
   - success rate diff
   - newly failed tasks
   - newly introduced invalid tool calls
   - newly introduced schema violations
   - retry budget exhaustion increase
7. 把真实 eval 作为 release gate 文档化。

Iteration 026 已完成：

1. 新增 CLI 命令：
   - `metis eval real-small-model --workspace . --output-root . --run-name latest`
2. CLI 行为：
   - 缺少 `METIS_BASE_URL` / `METIS_API_KEY` / `METIS_MODEL` 时返回 `2`
   - 缺少真实 endpoint 时不会伪造 eval 结果
   - eval 全部通过返回 `0`
   - eval 有失败返回 `1`
3. 稳定 eval run 目录新增 `manifest.json`。
4. manifest 记录：
   - suite
   - run_name
   - generated_at
   - success_rate
   - task_count
   - passed
   - failed
   - metadata
   - failed_tasks
5. 新增测试：
   - `tests/unit/test_cli_eval.py`
6. 更新测试：
   - `tests/e2e/test_local_9b_eval.py`
7. 定向测试通过：`5 passed, 3 skipped`。
8. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. `--run-name auto` 或默认 timestamped run name。
2. `latest` run manifest 指向最近一次 timestamped run。
3. `metis eval compare --current ... --baseline ...`。
4. failure-only report section。
5. release gate summary，便于 CI 直接判定是否准入。

Iteration 027 已完成：

1. 新增自动 run name helper：
   - `generate_real_small_model_eval_run_name()`
   - `resolve_real_small_model_eval_run_name()`
2. 支持自动别名：
   - `auto`
   - `timestamp`
   - `timestamped`
3. 自动 run name 使用 UTC timestamp：
   - 示例：`20260525-010203`
4. 新增 runs 根目录 helper：
   - `real_small_model_eval_runs_root()`
5. 新增 latest 指针路径 helper：
   - `real_small_model_eval_latest_pointer_path()`
6. `write_real_small_model_eval_reports()` 现在会：
   - 解析自动 run name
   - 写入 timestamped run 目录
   - 写入 `manifest.json`
   - 更新 `docs/evals/runs/latest.json`
7. `manifest.json` 新增：
   - `requested_run_name`
8. CLI 默认 `--run-name auto`。
9. 新增测试覆盖：
   - timestamp run name 生成
   - auto/timestamp/timestamped 解析
   - CLI 默认使用 auto
   - latest pointer 指向最新 resolved run
10. 定向测试通过：`8 passed, 3 skipped`。
11. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. `metis eval compare`：
   - 从两个 run 目录读取 `manifest.json` 与 `eval-report.json`
   - 输出 success_rate diff
   - 输出 newly failed tasks
   - 输出 recovered tasks
   - 输出 schema/tool/retry 指标变化
2. failure-only markdown section：
   - task id
   - status
   - errors
   - tool failure types
   - failure shape keys
3. release gate：
   - min success rate
   - max failed tasks
   - max invalid tool calls
   - max schema violations
   - max retry budget exhaustions

Iteration 028 已完成：

1. 新增 `metis/evals/compare.py`。
2. 新增 public helpers：
   - `load_eval_run()`
   - `compare_eval_runs()`
   - `eval_run_comparison_to_markdown()`
   - `write_eval_run_comparison()`
3. 新增 CLI：
   - `metis eval compare --baseline <run-dir> --current <run-dir>`
4. CLI 支持：
   - `--output-dir`
   - `--json`
5. compare 读取：
   - `manifest.json`
   - `eval-report.json`
6. compare 输出：
   - success_rate_delta
   - newly_failed_tasks
   - recovered_tasks
   - still_failed_tasks
   - new_tasks
   - removed_tasks
   - metric_deltas
   - regressed_metrics
   - has_regression
7. 回归判定：
   - success rate 下降
   - baseline 通过但 current 失败
   - 负向指标增加
8. 负向指标包括：
   - parser failures
   - tool failures
   - quality failures
   - false completion
   - final unverified
   - duplicate tool calls
   - invalid tool calls
   - policy blocks
   - evidence resolution failures
   - schema violations
   - schema repair failures
   - tool repair failures
   - retry budget exhaustions
   - pre-dispatch blocks
   - trajectory failures
9. 新增测试：
   - `tests/unit/test_eval_compare.py`
10. 更新测试：
   - `tests/unit/test_cli_eval.py`
11. 定向测试通过：`8 passed`。
12. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. release gate command：
   - `metis eval gate --run <run-dir>`
   - `--min-success-rate`
   - `--max-failed-tasks`
   - `--max-invalid-tool-calls`
   - `--max-schema-violations`
   - `--max-retry-budget-exhaustions`
2. failure-only eval report section：
   - 只展示失败任务
   - 错误列表
   - failure shape keys
   - tool failure types
3. latest 自动比较：
   - 当前 run 和 `latest.json` 指针中的上一轮 run 比较
4. 轨迹导出：
   - 对 regressed task 写出 trace JSON

Iteration 029 已完成：

1. 新增 `metis/evals/gate.py`。
2. 新增 public helpers：
   - `evaluate_eval_run_gate()`
   - `eval_gate_to_markdown()`
   - `write_eval_gate_report()`
   - `DEFAULT_GATE_THRESHOLDS`
3. 新增 CLI：
   - `metis eval gate --run <run-dir>`
4. CLI 支持：
   - `--output-dir`
   - `--json`
   - `--min-success-rate`
   - `--max-failed-tasks`
   - `--max-invalid-tool-calls`
   - `--max-schema-violations`
   - `--max-retry-budget-exhaustions`
   - `--max-pre-dispatch-blocks`
   - `--max-trajectory-failures`
5. 默认 release gate 严格阈值：
   - success rate 必须为 100%
   - failed tasks 必须为 0
   - invalid tool calls 必须为 0
   - schema violations 必须为 0
   - retry budget exhaustions 必须为 0
   - pre-dispatch blocks 必须为 0
   - trajectory failures 必须为 0
6. gate 输出：
   - `gate.json`
   - `gate.md`
7. 新增测试：
   - `tests/unit/test_eval_gate.py`
8. 更新测试：
   - `tests/unit/test_cli_eval.py`
9. 定向测试通过：`10 passed`。
10. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. failure-only eval report：
   - 在 `eval-report.md` 追加失败任务区块
   - 展示 errors
   - 展示 tool failure types
   - 展示 failure shape keys
2. gate + compare 联动：
   - 当前 run 自身必须过 gate
   - 当前 run 对 baseline 不得 regression
3. 自动链路：
   - `metis eval real-small-model --gate`
   - 运行后直接 gate
   - 可选 compare previous latest

Iteration 030 已完成：

1. `EvalSuiteResult.to_markdown()` 新增 `## Failure Details`。
2. 全部通过时显示：
   - `- None`
3. 存在失败时仅展开失败任务。
4. 每个失败任务包含：
   - status
   - turns used
   - tool calls
   - parser failures
   - tool failures
   - quality failures
   - invalid tool calls
   - schema violations
   - retry budget exhaustions
   - pre-dispatch blocks
   - trajectory failures
   - tool failure types
   - failure shape keys
   - errors
5. 新增测试覆盖：
   - 全成功 report 包含 failure details / none
   - 失败 report 仅展开失败任务
   - failure type、failure shape、errors 会进入 markdown
6. 定向测试通过：`27 passed`。
7. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. `metis eval real-small-model --gate`
   - 跑完 eval 自动 gate
   - gate 输出写入同一 run 目录或子目录
2. `metis eval real-small-model --compare-baseline <run-dir>`
   - 跑完 eval 自动 compare
3. `metis eval real-small-model --compare-latest`
   - 运行前读取 latest 指针作为 baseline
   - 运行后写当前 run
   - 执行 compare
4. failure trace export：
   - 每个失败任务单独 JSON
   - 包含 tool results、errors、metrics、evidence refs

Iteration 031 已完成：

1. `metis eval real-small-model` 新增：
   - `--gate`
   - `--gate-output-dir`
   - `--compare-baseline`
   - `--compare-latest`
   - `--compare-output-dir`
2. `--gate` 行为：
   - eval 写入当前 run 后执行 strict release gate
   - 默认输出到 `docs/evals/runs/<run-name>/gate/`
3. `--compare-baseline` 行为：
   - eval 写入当前 run 后对显式 baseline 执行 compare
   - 默认输出到 `docs/evals/runs/<run-name>/comparison/`
4. `--compare-latest` 行为：
   - 在当前 run 写入前读取旧的 `docs/evals/runs/latest.json`
   - 当前 run 写入后，用旧 latest 作为 baseline 执行 compare
   - 避免“当前 run 和自己比较”的假通过
5. 最终 exit code：
   - eval 失败 -> `1`
   - gate 失败 -> `1`
   - compare regression -> `1`
   - compare-latest 没有 previous latest -> `1`
   - endpoint 缺失仍为 `2`
6. 新增测试覆盖：
   - 自动 gate
   - 显式 baseline compare
   - latest compare 使用 previous pointer
   - latest pointer 缺失时失败
7. 定向测试通过：`11 passed`。
8. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. failed-task trace export：
   - `docs/evals/runs/<run-name>/failures/<task-id>.json`
   - metrics
   - errors
   - tool failure types
   - failure shape keys
2. manifest 增强：
   - provider model
   - base url host hash or redacted host
   - profile
   - task ids
   - git/worktree snapshot if available
3. budget gates：
   - max turns per task
   - max tool calls per task
   - max latency

Iteration 032 已完成：

1. `EvalSuiteResult.write_reports()` 新增 failure artifact export。
2. 每次 report 写入都会生成：
   - `failures/index.json`
3. 无失败时 index 内容：
   - `failure_count=0`
   - `artifacts=[]`
4. 有失败时，每个失败任务生成：
   - `failures/<safe-task-id>.json`
5. task id 会经过文件名安全化：
   - 非字母数字、`-`、`_`、`.` 字符替换为 `-`
6. 单任务 failure artifact 包含：
   - task id
   - success
   - status
   - turns used
   - tool calls
   - latency
   - parser/tool/quality/finalization/schema/retry/trajectory metrics
   - tool repair metrics by type
   - tool failure types
   - failure shape keys
   - errors
7. 新增测试覆盖：
   - 全成功仍写 `failures/index.json`
   - 失败任务写独立 JSON
   - 文件名安全化
   - metrics/errors/failure types/shape keys 写入 payload
8. 定向测试通过：`28 passed`。
9. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. failure artifact 增强：
   - task spec/prompt
   - required/forbidden tools
   - required evidence sources
   - gate thresholds
2. failure clustering：
   - 按 tool failure type 聚类
   - 按 failure shape key 聚类
   - 按 trajectory error 聚类
3. repair recommendation：
   - schema failure -> tighten prompt/tool schema feedback
   - retry budget exhaustion -> improve lineage block or tool hint
   - evidence failure -> improve evidence instruction and finalization

Iteration 033 已完成：

1. 新增 `metis/evals/failures.py`。
2. 新增 public helpers：
   - `cluster_failure_artifacts()`
   - `failure_clusters_to_markdown()`
   - `write_failure_clusters()`
3. `EvalSuiteResult.write_reports()` 现在会写：
   - `failures/index.json`
   - `failures/<safe-task-id>.json`
   - `failures/clusters.json`
   - `failures/clusters.md`
4. 无失败时 cluster 输出：
   - `failure_count=0`
   - `cluster_count=0`
   - `clusters=[]`
5. 当前聚类维度：
   - tool failure type
   - failure shape key
   - trajectory failure
   - schema failure
   - retry budget failure
   - evidence resolution failure
   - unverified finalization
   - unknown failure fallback
6. 每个 cluster 包含：
   - cluster key
   - count
   - task ids
   - signals
   - deterministic remediation
7. remediation 示例：
   - schema failure -> tighten schema feedback / argument examples / schema repair gates
   - retry budget failure -> improve lineage blocking / reduce repeated retries / task recovery hints
   - evidence failure -> improve evidence ref propagation / require existing evidence ids
   - trajectory failure -> review oracle gates / required tool order / prompt constraints
8. 新增测试：
   - `tests/unit/test_failure_clusters.py`
9. 更新测试：
   - `tests/unit/test_eval_runner.py`
10. 定向测试通过：`30 passed`。
11. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. remediation backlog：
   - `failures/remediation-backlog.json`
   - `failures/remediation-backlog.md`
   - 按 cluster 生成行动项
2. 每个 backlog item 包含：
   - cluster key
   - severity
   - owner area
   - recommended action
   - suggested eval/test
   - affected task ids
3. cluster gates：
   - no new critical clusters
   - max cluster count by type
   - compare clusters across runs

Iteration 034 已完成：

1. `metis/evals/failures.py` 新增：
   - `build_remediation_backlog()`
   - `remediation_backlog_to_markdown()`
   - `write_remediation_backlog()`
2. `write_failure_clusters()` 现在会自动写：
   - `failures/remediation-backlog.json`
   - `failures/remediation-backlog.md`
3. 每个 backlog item 包含：
   - id
   - cluster key
   - severity
   - owner area
   - affected task ids
   - recommended action
   - suggested eval
   - signals
4. 当前 severity 规则：
   - critical：schema / retry budget / evidence resolution / finalization unverified
   - high：trajectory failure / failure shape / count >= 3
   - medium：其他确定性 failure cluster
5. 当前 owner areas：
   - tool-schema-and-repair
   - runtime-lineage-and-recovery
   - evidence-and-finalization
   - tool-command-execution
   - eval-oracles-and-prompts
   - harness-runtime
6. suggested eval 规则覆盖：
   - schema repair eval
   - lineage regression eval
   - verified-final eval
   - command-recovery eval
   - trajectory oracle eval
7. 更新测试：
   - `tests/unit/test_failure_clusters.py`
   - `tests/unit/test_eval_runner.py`
8. 定向测试通过：`30 passed`。
9. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. cluster gate：
   - gate fail on critical remediation items
   - gate fail on cluster_count > threshold
   - gate fail on new critical cluster vs baseline
2. backlog comparison：
   - newly introduced clusters
   - resolved clusters
   - severity changes
3. failure artifact 增强：
   - task spec metadata
   - compact tool result excerpts

Iteration 035 已完成：

1. `evaluate_eval_run_gate()` 新增 cluster-aware thresholds：
   - `max_failure_clusters`
   - `max_critical_remediations`
2. 默认严格阈值：
   - `max_failure_clusters=0`
   - `max_critical_remediations=0`
3. gate 新增 aggregates：
   - `failure_clusters`
   - `critical_remediations`
4. gate 新增 `cluster_summary`：
   - cluster_count
   - cluster_keys
   - critical_remediations
   - critical_cluster_keys
5. gate 会读取：
   - `failures/clusters.json`
   - `failures/remediation-backlog.json`
6. 兼容旧 run：
   - 若 cluster/backlog 文件不存在，按 0 cluster 处理
7. CLI 新增参数：
   - `--max-failure-clusters`
   - `--max-critical-remediations`
8. 新增测试覆盖：
   - 默认旧 run 无 cluster 文件仍可评估
   - task 阈值放宽但 critical cluster 仍阻断
   - cluster 阈值显式放宽可通过
   - CLI 参数传递
9. 定向测试通过：`16 passed`。
10. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. cluster comparison：
   - baseline/current cluster keys
   - newly introduced critical clusters
   - resolved clusters
   - severity changes
2. compare 输出 cluster diff：
   - `new_clusters`
   - `resolved_clusters`
   - `new_critical_clusters`
3. compare gate 联动：
   - fail on new critical cluster
   - fail on critical cluster count increase

Iteration 036 已完成：

1. `compare_eval_runs()` 新增 cluster artifact 读取：
   - `failures/clusters.json`
   - `failures/remediation-backlog.json`
2. compare 输出新增 `cluster_diff`：
   - `new_clusters`
   - `resolved_clusters`
   - `shared_clusters`
   - `new_critical_clusters`
   - `resolved_critical_clusters`
   - `shared_critical_clusters`
3. `has_regression` 新增判定：
   - 出现新的 critical cluster 时，即使 success rate 没下降、task 没新增失败、metric 没变坏，也判定为 regression。
4. 非 critical 新 cluster 的行为：
   - 写入报告和 JSON，供人工/自动 triage；
   - 不单独触发 regression，避免把所有新发现都变成硬阻断。
5. Markdown comparison 新增 `## Cluster Changes` 区块。
6. 新增测试覆盖：
   - 新 critical cluster 会触发 regression；
   - resolved critical cluster 会进入输出；
   - 非 critical 新 cluster 会被记录但不触发 regression；
   - markdown 包含 cluster changes。
7. 定向测试通过：`5 passed`。
8. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. severity-change comparison：
   - high -> critical 必须视为 regression；
   - critical -> high/medium 视为改善；
   - 同一 cluster 的 severity 变化需要进入 JSON/Markdown。
2. cluster count trend：
   - 同一 cluster 影响 task 数增加；
   - critical cluster 总数增加；
   - total cluster count 增加。
3. failure artifact 增强：
   - 写入 task spec 元数据；
   - 写入 required/forbidden tools；
   - 写入 evidence policy；
   - 写入 quality gate thresholds；
   - 写入 compact tool result excerpts。

Iteration 037 已完成：

1. cluster summary 新增 severity map：
   - 从 `failures/remediation-backlog.json` 读取每个 cluster 的 severity。
2. `cluster_diff` 新增：
   - `severity_changes`
   - `critical_severity_upgrades`
   - `severity_downgrades`
3. `has_regression` 新增判定：
   - 同一 cluster 从 medium/high 升级到 critical 时，判定 regression。
4. Markdown comparison 新增展示：
   - `Critical severity upgrades`
   - `Severity downgrades`
5. 新增测试覆盖：
   - high -> critical 会触发 regression；
   - critical -> high 会记录为 downgrade 且不触发 regression；
   - markdown 展示 severity change。
6. 定向测试通过：`7 passed`。
7. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. cluster count trend：
   - 同一 cluster 的 count 增加；
   - 同一 cluster 的 affected task 数增加；
   - critical cluster 总数增加。
2. compare profile：
   - strict：任何 cluster 增加都阻断；
   - release：critical 新增/升级阻断；
   - exploratory：只记录不阻断。
3. failure artifact 增强：
   - task spec metadata；
   - compact tool result excerpts；
   - prompt/instruction hash；
   - provider/model metadata。

Iteration 038 已完成：

1. cluster summary 新增数量维度：
   - `cluster_counts`
   - `cluster_affected_task_counts`
2. `cluster_diff` 新增：
   - `cluster_count_changes`
   - `cluster_count_increases`
   - `cluster_count_decreases`
   - `affected_task_count_changes`
   - `affected_task_count_increases`
   - `affected_task_count_decreases`
   - `critical_cluster_count_increases`
   - `critical_cluster_affected_task_increases`
3. `has_regression` 新增判定：
   - 当前 critical cluster 的 count 增加；
   - 当前 critical cluster 的 affected task count 增加。
4. 非 critical cluster count 增加：
   - 进入 JSON/Markdown；
   - 不单独触发 regression。
5. Markdown comparison 新增展示：
   - `Cluster count increases`
   - `Critical cluster count increases`
   - `Critical affected task increases`
6. 新增测试覆盖：
   - critical cluster count 增加会触发 regression；
   - critical affected task 增加会触发 regression；
   - noncritical count 增加只记录不阻断。
7. 定向测试通过：`9 passed`。
8. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. compare profiles：
   - `strict`：任何 cluster 新增、severity 升级、count 增加都阻断；
   - `release`：critical 新增、升级、扩大阻断；
   - `exploratory`：只记录，不阻断。
2. CLI 支持 compare profile：
   - `metis eval compare --profile release`
   - `metis eval real-small-model --compare-latest --compare-profile release`
3. failure artifact 增强：
   - task spec metadata；
   - compact tool-result excerpts；
   - prompt/instruction hash；
   - provider/model metadata。

Iteration 039 已完成：

1. `compare_eval_runs()` 新增 profile 参数：
   - `release`
   - `strict`
   - `exploratory`
2. comparison 输出新增：
   - `profile`
   - `regression_reasons`
3. `release` profile：
   - 阻断 task/metric regression；
   - 阻断 new critical cluster；
   - 阻断 critical severity upgrade；
   - 阻断 critical cluster count increase；
   - 阻断 critical affected task increase。
4. `strict` profile：
   - 包含 release 全部阻断；
   - 额外阻断任何 new cluster；
   - 阻断任何 severity upgrade；
   - 阻断任何 cluster count increase；
   - 阻断任何 affected task count increase。
5. `exploratory` profile：
   - 记录所有 diff；
   - 不设置 `has_regression=True`；
   - 用于研究和不稳定 suite 的观察性比较。
6. CLI 新增：
   - `metis eval compare --profile strict|release|exploratory`
   - `metis eval real-small-model --compare-profile strict|release|exploratory`
7. 新增测试覆盖：
   - strict 会阻断 noncritical new cluster；
   - exploratory 会记录 task/metric regression 但不阻断；
   - CLI 会传递 compare profile；
   - CLI exit code 由 profile 后的 `has_regression` 控制。
8. 定向测试通过：
   - `tests/unit/test_eval_compare.py`：`11 passed`
   - `tests/unit/test_cli_eval.py`：`13 passed`
9. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. failure artifact 增强：
   - task spec metadata；
   - prompt；
   - required tools；
   - forbidden tools；
   - required evidence sources；
   - quality gates。
2. compact tool result excerpts：
   - 保存失败工具调用的短摘要；
   - 保存 schema/policy/runtime failure metadata；
   - 避免必须打开完整 trace 才能定位失败。
3. comparison summary 增强：
   - 将 regression reasons 分组输出；
   - 对每个 reason 链接相关 task/cluster。

Iteration 040 已完成：

1. `EvalSuiteResult` 新增 `task_specs`：
   - key 为 task id；
   - value 为 `EvalTaskSpec`。
2. `EvalRunner.run_suite()` 自动写入 task spec map。
3. failure artifact 新增 `task_spec`：
   - prompt；
   - allowed tools；
   - max turns；
   - expected artifacts；
   - required evidence sources；
   - quality gates；
   - require verified final；
   - required tools；
   - forbidden tools；
   - required tool order；
   - required tool arguments；
   - schema/policy/evidence/retry/pre-dispatch/failure-shape 阈值。
4. `failures/index.json` artifact entry 新增：
   - `has_task_spec`
5. 新增测试覆盖：
   - `run_suite()` 产生的失败 artifact 会携带完整 task spec metadata。
6. 定向测试通过：`tests/unit/test_eval_runner.py`：`29 passed`。
7. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. compact tool result excerpts：
   - tool name；
   - status；
   - failure type；
   - recoverable；
   - retry metadata；
   - schema errors；
   - content/error preview。
2. task spec hash：
   - prompt hash；
   - constraints hash；
   - 用于 baseline 比较时发现 eval 本身是否变动。
3. clustering 使用 task spec 信号：
   - required tool missing；
   - forbidden tool used；
   - evidence source missing；
   - tool order broken。

Iteration 041 已完成：

1. `EvalResult` 新增：
   - `tool_result_excerpts`
2. `EvalRunner.run_task()` 自动记录工具结果压缩摘要。
3. failure artifact 新增：
   - `tool_result_excerpts`
4. 每条 excerpt 包含：
   - index；
   - tool name；
   - tool call id；
   - status；
   - failed；
   - selected metadata；
   - content preview；
   - error preview。
5. selected metadata 包含：
   - failure_type；
   - recoverable；
   - retry_allowed；
   - retry_budget_exhausted；
   - pre_dispatch_block；
   - schema_valid；
   - schema_errors；
   - failure_shape_key；
   - policy_decision；
   - repair_instruction。
6. 摘要边界：
   - 最多前 20 条 tool result；
   - content/error preview 每条最多 500 字符。
7. 新增测试覆盖：
   - schema validation failed 的工具结果会写入 excerpt；
   - excerpt 保留真实 schema error、failure type、status、tool_call_id。
8. 定向测试通过：`tests/unit/test_eval_runner.py`：`30 passed`。
9. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. task spec hash：
   - prompt hash；
   - constraints hash；
   - full task spec hash。
2. provider/model/run metadata：
   - provider；
   - model；
   - profile；
   - suite；
   - run name。
3. clustering 增强：
   - 从 excerpt metadata 中直接读取 schema_errors；
   - 形成更细的 schema error cluster；
   - 将 policy/retry/pre-dispatch 分开聚类。

Iteration 042 已完成：

1. failure artifact 新增 `task_spec_hashes`：
   - `prompt_hash`
   - `constraints_hash`
   - `task_spec_hash`
2. hash 策略：
   - SHA-256；
   - JSON 使用稳定 key ordering；
   - prompt hash 只覆盖 prompt；
   - constraints hash 排除 task id 和 prompt；
   - task spec hash 覆盖完整 task spec。
3. failure artifact 新增：
   - `run_metadata`
4. 新增测试覆盖：
   - task spec hash 存在；
   - hash 为 64 位 SHA-256；
   - run metadata 写入失败 artifact。

Iteration 043 已完成：

1. clustering 开始读取：
   - `tool_result_excerpts`
   - `task_spec`
   - `task_spec_hashes`
   - `run_metadata`
2. 新增 cluster family：
   - `schema_error:*`
   - `tool_policy_decision:*`
   - `task_constraint:required_tool_missing`
   - `task_constraint:forbidden_tool_used`
   - `task_constraint:tool_order_broken`
   - `task_constraint:tool_arguments_missing`
   - `task_constraint:evidence_source_missing`
3. cluster signals 新增：
   - task spec hashes；
   - run suite/model/profile；
   - tool excerpt status；
   - excerpt failure type；
   - excerpt policy decision；
   - excerpt failure shape key；
   - schema errors。
4. remediation / severity / owner area / suggested eval 规则同步扩展。
5. 定向测试通过：`tests/unit/test_eval_runner.py tests/unit/test_failure_clusters.py`：`33 passed`。
6. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. compare task hash drift：
   - prompt changed；
   - constraints changed；
   - task spec changed。
2. compare reason linking：
   - 每个 regression reason 关联 task ids；
   - 关联 artifact path；
   - 关联 cluster key。
3. failure diagnosis report：
   - cluster；
   - task contract；
   - tool excerpt；
   - suggested repair eval。

Iteration 044 已完成：

1. `EvalSuiteResult.write_reports()` 新增：
   - `task-specs.json`
2. `task-specs.json` 覆盖所有 `run_suite()` task：
   - task id；
   - full task spec；
   - prompt hash；
   - constraints hash；
   - full task spec hash。
3. `compare_eval_runs()` 新增 task spec hash 读取：
   - 优先读取 `task-specs.json`；
   - 兼容旧 run，从 failed-task artifact 回退读取。
4. comparison 输出新增 `task_spec_diff`：
   - `baseline_task_specs`
   - `current_task_specs`
   - `prompt_changed`
   - `constraints_changed`
   - `task_spec_changed`
   - `missing_baseline_specs`
   - `missing_current_specs`
5. Markdown 新增：
   - `## Task Spec Drift`
6. profile 策略：
   - `release`：报告 task spec drift，不阻断；
   - `strict`：task spec drift / spec missing 会阻断；
   - `exploratory`：只记录。
7. 定向测试通过：`tests/unit/test_eval_compare.py tests/unit/test_eval_runner.py`：`43 passed`。
8. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. regression reason linking：
   - reason -> task ids；
   - reason -> cluster keys；
   - reason -> failure artifact paths。
2. provider/model drift compare：
   - model；
   - base_url；
   - profile；
   - suite task_count。
3. failure diagnosis report：
   - 以 task 为单位汇总 contract、tool excerpt、cluster、backlog action。

Iteration 045 已完成：

1. run summary 新增：
   - suite；
   - model；
   - base_url；
   - profile；
   - task_count。
2. comparison 输出新增 `environment_diff`：
   - `suite_changed`
   - `model_changed`
   - `base_url_changed`
   - `profile_changed`
   - `task_count_changed`
3. Markdown 新增：
   - `## Environment Drift`
4. profile 策略：
   - `release`：报告 environment drift，不阻断；
   - `strict`：environment drift 会阻断；
   - `exploratory`：只记录。
5. 新增测试覆盖：
   - release 报告 model/base_url/profile drift 但不阻断；
   - strict 遇到 environment drift 会加入 `environment_changed` reason。
6. 定向测试通过：`tests/unit/test_eval_compare.py`：`15 passed`。
7. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. regression reason linking：
   - reason -> task ids；
   - reason -> cluster keys；
   - reason -> artifact paths。
2. failure diagnosis report：
   - task contract；
   - tool excerpts；
   - cluster/backlog；
   - suggested next eval。

Iteration 046 已完成：

1. `compare_eval_runs()` 新增：
   - `regression_reason_links`
2. task-level reason 现在关联：
   - task ids；
   - current failure artifact paths。
3. metric reason 现在关联：
   - task ids；
   - metric deltas；
   - current failure artifact paths。
4. cluster reason 现在关联：
   - cluster keys；
   - affected task ids；
   - current failure artifact paths。
5. task spec drift reason 现在关联：
   - task ids；
   - task spec hash changes；
   - missing baseline/current specs。
6. environment drift reason 现在关联：
   - changed fields；
   - baseline/current values。
7. Markdown 新增：
   - `## Regression Reason Links`
8. 新增测试覆盖：
   - task/metric regression reason links；
   - cluster regression reason links；
   - strict drift reason links。
9. 定向测试通过：`tests/unit/test_eval_compare.py`：`18 passed`。
10. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. `failure-diagnosis.md`：
   - 按 reason 汇总；
   - 展示 task ids；
   - 展示 artifact paths；
   - 展示 cluster keys；
   - 展示 suggested remediation。
2. `diagnosis.json`：
   - machine-readable；
   - 可供后续自动生成 repair task。

Iteration 047 已完成：

1. 新增 `eval_run_comparison_diagnosis()`。
2. 新增 `eval_run_diagnosis_to_markdown()`。
3. `write_eval_run_comparison()` 现在输出：
   - `comparison.json`
   - `comparison.md`
   - `diagnosis.json`
   - `diagnosis.md`
4. diagnosis entry 包含：
   - reason；
   - task ids；
   - cluster keys；
   - artifact paths；
   - changed fields；
   - metrics；
   - changes；
   - recommended action。
5. 新增测试覆盖：
   - diagnosis artifact 输出；
   - reason link 到 diagnosis entry 的转换；
   - recommended action 存在。
6. 定向测试通过：`tests/unit/test_eval_compare.py`：`19 passed`。
7. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. CLI diagnosis：
   - `metis eval diagnose --comparison <comparison-dir>`
2. diagnosis 与 backlog 关联：
   - reason -> remediation item；
   - cluster key -> owner area；
   - suggested eval -> repair task。

Iteration 048 已完成：

1. 新增 diagnosis 读取：
   - `load_eval_diagnosis()`
2. 新增 repair task 生成：
   - `build_repair_tasks_from_diagnosis()`
   - `repair_tasks_to_markdown()`
   - `write_repair_tasks()`
   - `diagnose_eval_comparison()`
3. CLI 新增：
   - `metis eval diagnose --comparison <comparison-dir>`
   - `metis eval diagnose --comparison <comparison-dir> --output-dir <repair-dir>`
   - `metis eval diagnose --comparison <comparison-dir> --json`
4. 输出新增：
   - `repair-tasks.json`
   - `repair-tasks.md`
5. repair task stub 包含：
   - id；
   - reason；
   - priority；
   - owner area；
   - task ids；
   - cluster keys；
   - artifact paths；
   - fields；
   - metrics；
   - changes；
   - recommended action；
   - suggested eval；
   - source backlog items。
6. cluster 相关 diagnosis 会读取 current run 的 remediation backlog：
   - severity -> priority；
   - owner_area；
   - recommended_action；
   - suggested_eval；
   - remediation item id。
7. 新增测试覆盖：
   - diagnosis 转 repair tasks；
   - backlog item 关联；
   - CLI diagnose markdown/json 输出。
8. 定向测试通过：`tests/unit/test_eval_compare.py tests/unit/test_cli_eval.py`：`36 passed`。
9. 编译检查通过：`python -m compileall -q metis`。

下一轮应优先补：

1. `metis eval repair-plan`：
   - 按 owner area 分组；
   - 按 priority 排序；
   - 给出 verification command。
2. trace timeline export：
   - repair task 指向具体 tool call / finalization step。
Iteration 061 completed:

1. Added eval registry inventory APIs:
   - `generic_eval_tool_inventory(workspace=...)`
   - `tool_inventory_to_markdown()`
   - `generic_eval_quality_gate_inventory()`
   - `quality_gate_inventory_to_markdown()`
2. Added CLI:
   - `metis eval list-tools --workspace <workspace>`
   - `metis eval list-tools --workspace <workspace> --json`
   - `metis eval list-quality-gates`
   - `metis eval list-quality-gates --json`
3. Tool inventory includes:
   - name
   - description
   - category
   - side effect
   - permission requirement
   - retry policy
   - verification label
   - metadata
   - parameter schema
4. Quality gate inventory includes:
   - name
   - description
   - failure policy
   - metadata
5. Targeted tests passed:
   - `python -m compileall -q metis`
   - `python -m pytest tests/unit/test_eval_suite_run.py tests/unit/test_cli_eval.py tests/unit/test_eval_suite_validation.py -q`
   - `51 passed`

Next iteration should prioritize:

1. predicate-vs-tool-schema validation:
   - inspect `required_tool_arguments`;
   - find referenced tool schema;
   - warn/error when expected argument keys do not exist;
   - validate simple predicate types against schema property types.
2. shared registry construction:
   - include builtin tools;
   - include adapter tools;
   - include plugin tools;
   - inventory, validation, and runtime should share one construction path.
3. inventory enrichment:
   - compact required argument list;
   - risk level;
   - shell use flag;
   - read/write side effects.
4. quality gate context schema:
   - document expected context fields per gate.
5. suite-scoped latest pointers.

Iteration 060 completed:

1. Added registry-aware suite validation:
   - `validate_eval_suite(path, available_tools=..., available_quality_gates=...)`
2. Added generic validation context:
   - `generic_eval_validation_context(workspace=...)`
   - builds active built-in tool registry for the workspace;
   - reads default quality gate names from `QualityGateRunner`.
3. Connected `run-suite` to registry-aware validation:
   - validates tool names before endpoint checks;
   - validates quality gate names before endpoint checks;
   - continues to fail before model calls on invalid suites.
4. Connected `validate-suite` to registry-aware validation:
   - added `--workspace`;
   - workspace controls the active built-in tool registry.
5. Added validation for tool references:
   - `allowed_tools`
   - `required_tools`
   - `forbidden_tools`
   - `required_tool_order`
   - `required_tool_arguments[*].tool`
   - `required_tool_arguments[*].tool_name`
6. Added validation for quality gate references:
   - `quality_gates`
7. Added list item validation:
   - string-list fields must contain non-empty strings;
   - `required_tool_arguments` remains a list of objects.
8. Targeted tests passed:
   - `python -m compileall -q metis`
   - `python -m pytest tests/unit/test_eval_suite_validation.py tests/unit/test_eval_suite_run.py tests/unit/test_cli_eval.py -q`
   - `45 passed`

Next iteration should prioritize:

1. registry inventory commands:
   - `metis eval list-tools --workspace <workspace>`
   - `metis eval list-quality-gates`
   - JSON and markdown output.
2. plugin/adapter registry construction:
   - shared path to build builtin + adapter + plugin tools;
   - validation should use the same registry as runtime execution.
3. tool argument predicate validation against tool schemas:
   - verify required argument keys exist in tool JSON schema;
   - warn when predicates reference impossible fields.
4. validation report enrichment:
   - include available tool/gate counts;
   - include optional inventories when requested.
5. suite-scoped latest pointers.

Iteration 059 completed:

1. Added suite validation module:
   - `metis.evals.suite_validation`
2. Added validation APIs:
   - `validate_eval_suite()`
   - `eval_suite_validation_to_markdown()`
   - `write_eval_suite_validation()`
3. Added CLI:
   - `metis eval validate-suite --suite <suite-json-or-dir>`
   - `metis eval validate-suite --suite <suite-json-or-dir> --json`
   - `metis eval validate-suite --suite <suite-json-or-dir> --output-dir <validation-dir>`
4. Connected validation into `run-suite`:
   - validates before endpoint env checks;
   - validates before model calls;
   - returns non-zero on invalid suite;
   - prints validation markdown;
   - explicitly states the eval was not run because suite validation failed.
5. Direct Python execution now validates too:
   - `run_generic_eval_suite()` raises `ValueError` on invalid suites.
6. Validation covers:
   - load failures;
   - top-level `tasks`;
   - non-empty task list;
   - string `schema_version`;
   - string `suite` or `name`;
   - wrapped `task_spec`;
   - required `id`;
   - required `prompt`;
   - duplicate task ids;
   - list/dict/bool/integer field types;
   - non-negative integer thresholds;
   - `max_turns >= 1`;
   - `required_tool_arguments` shape;
   - warnings for unknown ignored fields.
7. Targeted tests passed:
   - `python -m compileall -q metis`
   - `python -m pytest tests/unit/test_eval_suite_validation.py tests/unit/test_eval_suite_run.py tests/unit/test_cli_eval.py -q`
   - `42 passed`
8. Suite JSON readers now accept UTF-8 with BOM via `utf-8-sig`, fixing Windows-authored JSON suite files before validation.

Next iteration should prioritize:

1. registry-aware suite validation:
   - build active tool registry for a workspace;
   - validate `allowed_tools`, `required_tools`, `forbidden_tools`, `required_tool_order`, and required argument `tool` names;
   - validate `quality_gates` names.
2. publish JSON Schema:
   - generate or maintain `docs/schema/metis-eval-suite.schema.json`;
   - add schema version.
3. suite-scoped latest pointers:
   - `latest-by-suite.json`;
   - `--compare-latest-suite`.
4. CI summary artifact:
   - `ci-summary.json`;
   - includes validation/gate/comparison status and artifact paths.
5. matrix eval execution:
   - run same suite across multiple profiles/models.

Iteration 058 completed:

1. Added same-command comparison to generic `run-suite`:
   - `--compare-baseline <run-dir>`
   - `--compare-latest`
   - `--compare-output-dir <comparison-dir>`
   - `--compare-profile strict|release|exploratory`
2. `--compare-latest` behavior:
   - reads the previous `docs/evals/runs/latest.json` before writing the current run;
   - compares current run against that previous run;
   - returns non-zero and prints a clear message when no previous pointer exists.
3. Comparison output behavior:
   - default output is `<current-run>/comparison`;
   - writes `comparison.json`;
   - writes `comparison.md`;
   - writes `diagnosis.json`;
   - writes `diagnosis.md`.
4. Exit-code behavior:
   - model/gate failures remain non-zero;
   - comparison regressions also force non-zero exit.
5. Targeted tests passed:
   - `python -m compileall -q metis`
   - `python -m pytest tests/unit/test_cli_eval.py -q`
   - `29 passed`

Next iteration should prioritize:

1. suite schema validation before model calls:
   - explicit schema version;
   - required top-level fields;
   - required task fields;
   - validation markdown/JSON output.
2. suite-scoped latest pointers:
   - keep global latest;
   - add latest-by-suite index;
   - allow `--compare-latest-suite`.
3. CI summary:
   - write compact `ci-summary.json`;
   - include gate status, comparison status, regression reasons, and artifact paths.
4. matrix comparison:
   - compare same suite across models;
   - compare same suite across runtime profiles.
5. open-ended quality rubric extension:
   - deterministic gates remain mandatory;
   - judge/rubric scoring is additive only.

Iteration 057 completed:

1. Added a generic eval suite runner module:
   - `metis.evals.suite_run`
2. Added suite loading and metadata helpers:
   - `load_eval_suite_payload()`
   - `generic_eval_suite_metadata()`
   - `generic_eval_env_configured()`
3. Added generic runner construction:
   - `build_generic_eval_runner()`
   - OpenAI-compatible provider
   - built-in tools
   - SQLite state store
   - evidence ledger
   - configurable runtime profile
4. Added generic suite execution:
   - `run_generic_eval_suite()`
   - `run_and_write_generic_eval_suite()`
5. Added generic report writing:
   - `write_generic_eval_suite_reports()`
   - `generic_eval_suite_manifest()`
   - `write_generic_eval_latest_pointer()`
6. Added CLI:
   - `metis eval run-suite --suite <suite-json-or-dir>`
   - `metis eval run-suite --suite <suite-json-or-dir> --workspace <workspace> --output-root <output-root>`
   - `metis eval run-suite --suite <suite-json-or-dir> --run-name auto --profile small`
   - `metis eval run-suite --suite <suite-json-or-dir> --gate`
7. Safety behavior:
   - refuses to run unless `METIS_BASE_URL`, `METIS_API_KEY`, and `METIS_MODEL` are present;
   - explicitly states no model result was faked.
8. Targeted tests passed:
   - `python -m compileall -q metis`
   - `python -m pytest tests/unit/test_eval_suite_run.py tests/unit/test_cli_eval.py tests/unit/test_eval_runner.py -q`
   - `64 passed`

Next iteration should prioritize:

1. same-command baseline comparison:
   - `metis eval run-suite --suite <suite> --compare-baseline <run-dir>`
   - `metis eval run-suite --suite <suite> --compare-latest`
   - `--compare-output-dir`
   - `--compare-profile strict|release|exploratory`
2. suite schema validation:
   - explicit `schema_version`
   - required top-level fields
   - per-task validation report before model calls.
3. suite-scoped latest pointers:
   - preserve generic `latest.json`
   - add `latest.<suite>.json` or `latest-by-suite.json`.
4. benchmark import:
   - JSONL import for simple prompt suites;
   - OpenAI Evals-style data adapter;
   - scenario pack adapter.
5. judge/rubric extension:
   - optional rubric field;
   - deterministic gates first, judge scoring second;
   - never replace hard tool/evidence constraints with judge scoring.

Iteration 056 completed:

1. Added executable targeted eval suite materialization:
   - `load_eval_stubs()`
   - `materialize_eval_suite_from_stubs()`
   - `eval_suite_to_markdown()`
   - `write_materialized_eval_suite()`
   - `materialize_eval_suite()`
2. Added JSON suite loading into runtime task specs:
   - `eval_task_spec_from_dict()`
   - `eval_task_specs_from_suite_payload()`
   - `load_eval_task_specs()`
3. Added CLI:
   - `metis eval materialize-stubs --stubs <targeted-eval-stubs-json-or-dir>`
   - `metis eval materialize-stubs --stubs <targeted-eval-stubs-json-or-dir> --output-dir <suite-dir>`
   - `metis eval materialize-stubs --stubs <targeted-eval-stubs-json-or-dir> --json`
4. New materialized outputs:
   - `targeted-eval-suite.json`
   - `targeted-eval-suite.md`
5. Targeted tests passed:
   - `python -m compileall -q metis`
   - `python -m pytest tests/unit/test_eval_runner.py tests/unit/test_eval_compare.py tests/unit/test_cli_eval.py -q`
   - `85 passed`

Next iteration should prioritize:

1. generic eval suite runner:
   - `metis eval run-suite --suite <suite-json-or-dir>`
   - load with `load_eval_task_specs()`
   - write manifest/report/failure artifacts using the same run directory conventions.
2. suite schema versioning:
   - add `schema_version`
   - validate required fields before execution.
3. source rule extraction:
   - move repair-task source-module rules out of `compare.py`.
4. open-ended quality rubrics:
   - optional rubric field for deliverable quality;
   - deterministic gate first, judge-based scoring second.
5. external benchmark import:
   - adapters for existing JSONL/benchmark task formats so Metis can become a general harness base for different scenario agents.

Iteration 055 completed:

1. Added targeted eval stub generation:
   - `build_eval_stubs_from_repair_tasks()`
   - `eval_stubs_to_markdown()`
   - `write_eval_stubs()`
2. Added CLI:
   - `metis eval eval-stubs --repair-tasks <repair-tasks-json-or-dir>`
   - `metis eval eval-stubs --repair-tasks <repair-tasks-json-or-dir> --output-dir <stubs-dir>`
   - `metis eval eval-stubs --repair-tasks <repair-tasks-json-or-dir> --json`
3. Outputs:
   - `targeted-eval-stubs.json`
   - `targeted-eval-stubs.md`
4. Stub content includes:
   - source repair task id;
   - critical event ids;
   - likely source modules;
   - suggested assertion;
   - verification command;
   - eval task spec skeleton.
5. Targeted tests passed:
   - `python -m pytest -q tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py`
   - `47 passed`

Next iteration should prioritize:

1. executable eval stub materialization:
   - convert stubs into importable `EvalTaskSpec` definitions or JSON suite files.
2. focused verification command planner:
   - source modules -> exact test subset.
3. repair status workflow:
   - open -> in_progress -> fixed -> verified -> closed.

Iteration 054 completed:

1. Repair tasks now include:
   - `likely_source_modules`
2. Source-module mapping uses:
   - regression reason;
   - cluster keys;
   - metric names;
   - remediation owner area.
3. Initial mapping covers:
   - schema failures;
   - policy/approval/command failures;
   - retry/lineage/failure-shape failures;
   - evidence/finalization failures;
   - parser repair failures;
   - trajectory/task-constraint failures;
   - task spec/environment drift.
4. Repair plan owner-area summaries now include:
   - `critical_event_ids`
   - `likely_source_modules`
5. Repair plan markdown renders critical events and source modules.
6. Targeted tests passed:
   - `python -m pytest -q tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py`
   - `43 passed`

Next iteration should prioritize:

1. targeted eval stub generation:
   - repair task -> eval task skeleton.
2. verification command suggestions:
   - likely source modules -> focused test command.
3. source mapping extraction:
   - move mapping rules out of `compare.py` when rule count grows.

Iteration 053 completed:

1. Timeline helpers added:
   - `timeline_event_ids()`
   - `select_critical_event()`
   - `critical_event_id()`
2. Critical event selection now prioritizes:
   - failed finalization events;
   - failed tool events;
   - failed parser/finalization repair events;
   - error events.
3. Repair task generation now reads timeline files and adds:
   - `timeline_event_ids`
   - `critical_event_ids`
4. Repair task markdown now renders critical events.
5. Targeted tests passed:
   - `python -m pytest -q tests\unit\test_timeline.py tests\unit\test_eval_compare.py`
   - `29 passed`

Next iteration should prioritize:

1. repair plan event surfacing:
   - owner area summaries should include critical events.
2. source module mapping:
   - `tool.result` + `schema_validation_failed` -> `metis/tools/schema_validator.py`, `metis/tools/dispatcher.py`
   - `finalization.result` -> `metis/runtime/finalization.py`
   - `parser.repair.*` -> `metis/providers/parsers/*`
3. targeted eval stub generation:
   - repair task -> eval task template.

Iteration 052 completed:

1. `AgentRunResult` now carries:
   - `trace_events`
2. `AgentLoop` now records runtime-native events:
   - `agent.start`
   - `model.request`
   - `model.response`
   - `parser.repair.request`
   - `parser.repair.result`
   - `tool.request`
   - `tool.result`
   - `finalization.check`
   - `finalization.result`
   - `finalization.repair.request`
   - `finalization.repair.result`
   - `agent.error`
3. `EvalResult` now carries runtime trace events.
4. Failed eval timelines now prefer runtime trace events and fall back to synthetic events only when needed.
5. Timeline rendering now summarizes nested runtime attributes.
6. Targeted tests passed:
   - `python -m pytest -q tests\integration\test_parser_repair.py tests\integration\test_strict_output_block.py tests\integration\test_agent_loop_fake.py tests\unit\test_eval_runner.py tests\unit\test_timeline.py`
   - `37 passed`

Next iteration should prioritize:

1. critical event selection:
   - automatically identify the most likely failure boundary.
2. repair task event anchoring:
   - add `timeline_event_ids`
   - add `critical_event_id`
3. source-module mapping:
   - event/failure type -> likely Metis modules.
4. OTel-compatible export:
   - local JSON shape that can later map to GenAI spans.

Iteration 051 completed:

1. Added timeline module:
   - `metis.telemetry.timeline`
2. Added timeline helpers:
   - `load_timeline()`
   - `normalize_timeline()`
   - `timeline_to_markdown()`
   - `timeline_to_json()`
3. Added CLI:
   - `metis trace show --timeline <timeline.json>`
   - `metis trace show --timeline <timeline.json> --json`
   - `metis trace show --timeline <timeline.json> --include-payload`
4. Failed eval timeline events now include stable `event_id`.
5. Targeted tests passed:
   - `python -m pytest -q tests\unit\test_timeline.py tests\unit\test_cli_eval.py tests\unit\test_eval_runner.py tests\unit\test_eval_compare.py`
   - `76 passed`

Next iteration should prioritize:

1. runtime trace event enrichment:
   - `model.request`
   - `model.response`
   - `parser.repair.request`
   - `parser.repair.result`
   - `tool.request`
   - `tool.policy_decision`
   - `finalization.check`
   - `finalization.result`
2. repair task event anchoring:
   - `timeline_event_ids`
   - `critical_event_id`
3. OpenTelemetry-compatible field names:
   - model name
   - token usage
   - tool name
   - status
   - latency

Iteration 050 completed:

1. Failed eval artifact export now writes compact timelines:
   - `<task>.timeline.json`
   - `<task>.timeline.md`
2. Failure index entries now include:
   - `timeline_path`
   - `timeline_markdown_path`
3. Failure artifacts now include:
   - `timeline_path`
4. Timeline events currently include:
   - `task.start`
   - `tool.result`
   - `error`
   - `task.end`
5. Comparison reason links now carry `timeline_paths` when available.
6. Diagnosis entries now carry `timeline_paths`.
7. Repair tasks now carry and render `timeline_paths`.
8. Targeted tests passed:
   - `python -m pytest -q tests\unit\test_eval_runner.py tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py`
   - `71 passed`

Next iteration should prioritize:

1. trace event enrichment:
   - model input/output event;
   - tool request event;
   - parser repair event;
   - policy decision event;
   - finalization gate event.
2. stable event ids:
   - repair tasks should point to exact timeline event indexes or span ids.
3. `metis trace show`:
   - CLI inspection for timeline JSON/Markdown.

Iteration 049 completed:

1. Added repair task loading:
   - `load_repair_tasks()`
   - accepts `repair-tasks.json` or a directory containing it.
2. Added repair plan generation:
   - `build_repair_plan()`
   - `repair_plan_to_markdown()`
   - `write_repair_plan()`
   - `plan_repairs()`
3. CLI added:
   - `metis eval repair-plan --repair-tasks <repair-tasks-json-or-dir>`
   - `metis eval repair-plan --repair-tasks <repair-tasks-json-or-dir> --output-dir <plan-dir>`
   - `metis eval repair-plan --repair-tasks <repair-tasks-json-or-dir> --json`
4. Repair plan output added:
   - `repair-plan.json`
   - `repair-plan.md`
5. Repair plan schema includes:
   - priority buckets
   - owner-area groups
   - execution phases
   - next actions
   - sorted repair tasks
6. Targeted tests passed:
   - `python -m pytest -q tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py`
   - `41 passed`

Next iteration should prioritize:

1. trace timeline export:
   - every failed eval should have a compact timeline artifact;
   - repair tasks should link to exact tool calls, schema repairs, policy decisions, and finalization checks.
2. repair task to source-module mapping:
   - cluster and reason should suggest likely Metis modules.
3. targeted eval generation:
   - each repair task should be convertible into an eval stub.
## Latest Progress: Iteration 146 - Repair execute preflight attestation

This iteration makes repair-execute preflight decisions tamper-evident.

Problem:

1. Iteration 145 wrote `repair-execute-preflight.json` and `.md`.
2. Those artifacts are control-plane approval decisions.
3. If edited after generation, a later CI step or repair executor could trust a false readiness result.

Completed:

1. `metis eval repair-execute --output-dir <directory>` now also writes:
   - `repair-execute-preflight-attestation.json`
   - `repair-execute-preflight-attestation.md`
2. Added attestation helpers for artifact type:
   - `repair-execute-preflight`
3. Added CLI command:
   - `metis eval verify-repair-preflight --preflight-dir <directory>`
4. The command supports `--json`.
5. Updated CI recipe, 9B eval report, and documentation regression tests.
6. Added CLI tests for passing and failing preflight verification.

Harness meaning:

1. The approval decision before repair execution is now itself auditable.
2. Future repair executors can require verified preflight artifacts.
3. This further reduces the chance that a 9B model acts on stale or tampered control-plane state.

Verification:

- Focused CLI/doc tests are run for this batch.

New task gaps:

1. Add a dedicated repair execution command behind this verified preflight.
2. Persist repair attempt status back into repair-plan tasks and phases.
3. Add signed attestation support.

## Latest Progress: Iteration 145 - Repair execute preflight artifacts

This iteration makes repair execution readiness durable.

Problem:

1. Iteration 144 added `metis eval repair-execute`.
2. The preflight result only printed to stdout.
3. CI and dashboards need a stable artifact to archive, inspect, and consume.

Completed:

1. Added `--output-dir` to `metis eval repair-execute`.
2. The command now writes:
   - `repair-execute-preflight.json`
   - `repair-execute-preflight.md`
3. The JSON artifact preserves:
   - operation;
   - ready flag;
   - requested phase;
   - plan/stubs/suite directories;
   - per-check pass/fail status;
   - failure count;
   - failure list.
4. Updated the CI recipe and 9B eval report.
5. Added CLI test assertions for written preflight artifacts.

Harness meaning:

1. Repair readiness is now auditable and machine-readable.
2. Future repair execution can persist evidence before invoking a model or tool.
3. CI can archive the exact decision that allowed or blocked repair execution.

Verification:

- Focused CLI/doc tests are run for this batch.

New task gaps:

1. Add attestation for preflight artifacts.
2. Persist repair attempt status back into repair plan tasks and phases.
3. Implement actual repair execution behind the preflight.

## Latest Progress: Iteration 144 - Repair execute preflight

This iteration adds a single pre-execution safety gate for future repair executors.

Problem:

1. Repair safety checks were available as separate commands and helpers.
2. A future repair executor would need to remember to verify plan attestation, check phase executability, verify stubs, and verify suite artifacts before doing work.
3. That orchestration should be deterministic and centralized.

Completed:

1. Added `metis eval repair-execute`.
2. Required inputs:
   - `--plan-dir`
   - `--phase`
3. Optional inputs:
   - `--stubs-dir`
   - `--suite-dir`
4. The command does not edit files and does not invoke a model.
5. It checks:
   - repair-plan attestation;
   - repair-plan JSON load;
   - requested phase executability;
   - targeted eval stubs attestation when provided;
   - targeted eval suite attestation when provided.
6. It returns `0` only when every requested check passes.
7. It supports Markdown and JSON output with per-check status and failure details.
8. Updated CI recipe and 9B eval report.
9. Added CLI tests for success, blocked phase failure, and plan attestation failure.

Harness meaning:

1. Future repair execution now has a single deterministic readiness gate.
2. 9B model calls can be kept downstream of verified plan/stub/suite artifacts and executable phase status.
3. This centralizes orchestration safety instead of spreading it across model prompts or ad hoc scripts.

Verification:

- This batch uses focused CLI/doc/attestation tests rather than full-suite testing, per the updated iteration strategy.

New task gaps:

1. Implement actual repair execution behind the preflight.
2. Persist repair attempt status back into repair-plan tasks/phases.
3. Add signed attestation support.
4. Add GitHub Actions and local PowerShell examples.

## Latest Progress: Iteration 143 - Targeted suite run attestation gate

This iteration enforces targeted suite attestation before execution.

Problem:

1. Iteration 142 made targeted eval suite attestation independently verifiable.
2. `metis eval run-suite` could still run a materialized targeted suite without first checking that attestation.
3. A generated targeted suite is an executable regression contract; running it after tampering can mislead repair loops and small models.

Completed:

1. `metis eval run-suite` now detects materialized targeted suites:
   - `--suite <directory>` containing `targeted-eval-suite.json`;
   - `--suite <path>/targeted-eval-suite.json`.
2. For those suites, the CLI runs `verify_targeted_eval_suite_attestation(suite_dir)` before endpoint checks or model execution.
3. If verification fails, the eval is not run and the command returns `1`.
4. Generic eval suites are unaffected.
5. Added CLI tests for failed attestation and successful verification-before-run.
6. Updated the 9B eval report and CI recipe with the execution gate and explicit attestation artifact names.

Harness meaning:

1. Generated repair eval contracts must verify before execution.
2. 9B model calls remain downstream of deterministic artifact trust.
3. The repair loop now protects:
   - plan artifacts;
   - targeted eval stubs;
   - materialized targeted suites;
   - targeted suite execution.

Verification:

- Targeted CLI/doc tests are run after this batch rather than after each individual patch, following the updated iteration strategy.

New task gaps:

1. Add a dedicated repair execution command that composes verified plan, verified stubs, verified suite, and phase enforcement.
2. Add signed attestation support.
3. Add GitHub Actions and local PowerShell examples.

## Latest Progress: Iteration 142 - Repair eval artifact verification CLI

This iteration exposes targeted repair eval artifact verification through the CLI.

Problem:

1. Iteration 141 added attestation for targeted eval stubs and materialized targeted suites.
2. CI still needed standalone commands to verify those artifacts without importing Python helpers.
3. Generated repair eval contracts must be verified before later materialization, review, or execution.

Completed:

1. Added:
   - `metis eval verify-eval-stubs --stubs-dir <directory>`
   - `metis eval verify-targeted-suite --suite-dir <directory>`
2. Both commands support `--json`.
3. `verify-eval-stubs` calls `verify_targeted_eval_stubs_attestation()`.
4. `verify-targeted-suite` calls `verify_targeted_eval_suite_attestation()`.
5. Exit behavior:
   - `0` when verification passes;
   - `1` when verification fails.
6. Markdown and JSON outputs preserve artifact label, directory, verified flag, failure count, and failure list.
7. Updated `docs/evals/repair-plan-ci-recipe.md` with repair eval artifact verification steps.
8. Updated the documentation regression test to require the new commands and attestation names.

Harness meaning:

1. The repair artifact trust chain is now available from CLI:
   - repair plan verification;
   - targeted eval stubs verification;
   - targeted eval suite verification.
2. CI can block before generated eval contracts are consumed.
3. 9B model calls remain downstream of deterministic artifact verification.

Verification:

- `python -m pytest tests\unit\test_cli_eval.py -q`: `48 passed`

New task gaps:

1. Enforce targeted suite attestation before running repair eval suites.
2. Add signed attestation support.
3. Add GitHub Actions and local PowerShell examples.
4. Add a dedicated repair execution command that consumes verified plan and eval artifacts.

## Latest Progress: Iteration 141 - Repair eval artifact attestation

This iteration extends local attestation beyond repair plans into generated repair eval artifacts.

Problem:

1. Repair plans are now attested and independently verifiable.
2. The artifacts generated after a plan were still unaudited:
   - targeted eval stubs;
   - materialized targeted eval suites.
3. These artifacts are executable regression contracts.
4. If they are modified after generation, a repair loop can run against stale or tampered eval definitions.

Completed:

1. Added repair eval artifact attestation helpers:
   - `build_repair_eval_artifact_attestation()`
   - `write_targeted_eval_stubs_attestation()`
   - `write_targeted_eval_suite_attestation()`
   - `verify_targeted_eval_stubs_attestation()`
   - `verify_targeted_eval_suite_attestation()`
   - `repair_eval_artifact_attestation_to_markdown()`
2. Added predicate type:
   - `https://metis.local/attestations/repair-eval-artifacts/v1`
3. `write_eval_stubs()` now writes:
   - `targeted-eval-stubs.json`
   - `targeted-eval-stubs.md`
   - `targeted-eval-stubs-attestation.json`
   - `targeted-eval-stubs-attestation.md`
4. `write_materialized_eval_suite()` now writes:
   - `targeted-eval-suite.json`
   - `targeted-eval-suite.md`
   - `targeted-eval-suite-attestation.json`
   - `targeted-eval-suite-attestation.md`
5. Verification checks:
   - attestation exists;
   - statement type and predicate type are correct;
   - artifact type matches expected wrapper;
   - subject list is present;
   - self-subjects are rejected;
   - subject files exist;
   - SHA256 digests and sizes match;
   - required JSON and Markdown subjects are present.
6. Tests verify immediate success and digest drift detection for both stubs and suite artifacts.

Harness meaning:

1. The repair trust chain now covers generated regression contracts.
2. A 9B model is not asked to repair against unaudited targeted eval artifacts.
3. Future CI can verify each artifact boundary independently:
   - run artifact attestation;
   - repair plan attestation;
   - targeted eval stubs attestation;
   - targeted eval suite attestation.

Verification:

- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_run_attestation.py -q`: `62 passed`

New task gaps:

1. Add CLI verification commands for targeted eval stubs and materialized suites.
2. Add CI recipe steps for repair eval artifact verification.
3. Add signed attestation support.
4. Add attestation verification before running materialized targeted eval suites.

## Latest Progress: Iteration 140 - Repair plan CI recipe

This iteration turns the repair-plan enforcement features into a documented CI workflow.

Problem:

1. Iterations 136-139 added phase enforcement, repair-plan attestation, attestation enforcement, and standalone verification.
2. The correct command order was spread across iteration notes.
3. CI needs a single recipe to avoid running valid commands in an unsafe sequence.

Completed:

1. Added `docs/evals/repair-plan-ci-recipe.md`.
2. The recipe defines the standard sequence:
   - `metis eval compare`
   - `metis eval diagnose`
   - `metis eval repair-plan`
   - `metis eval verify-repair-plan`
   - `metis eval repair-plan --require-executable-phase <phase-id>`
3. The recipe documents:
   - required inputs;
   - expected artifacts;
   - precondition phases;
   - recommended CI policy;
   - why 9B model calls must remain downstream of deterministic trust checks.
4. Updated the 9B eval report to link the recipe.
5. Added documentation regression test `test_repair_plan_ci_recipe_covers_verified_phase_workflow`.

Harness meaning:

1. The safe repair sequence is now operational, not just implemented.
2. Humans, CI, and future agent executors can follow the same command order.
3. The workflow explicitly prevents invoking a model on a blocked phase or from an unattested repair plan.

Verification:

- `python -m pytest tests\unit\test_docs_exist.py -q`: expected focused validation for the new recipe.

New task gaps:

1. Add a dedicated repair execution command that consumes the verified phase workflow.
2. Add attestation for targeted eval stubs and materialized suites.
3. Add signed attestation support.
4. Add GitHub Actions and local PowerShell CI examples.

## Latest Progress: Iteration 139 - Verify repair plan CLI

This iteration adds standalone repair-plan attestation verification to the CLI.

Problem:

1. Iteration 138 verified repair-plan attestation only as part of phase enforcement.
2. CI may need to verify an existing repair-plan artifact bundle without regenerating the plan.
3. Artifact trust boundaries should be independently runnable and composable.

Completed:

1. Added CLI command:
   - `metis eval verify-repair-plan --plan-dir <directory>`
2. The command calls `verify_repair_plan_attestation(plan_dir)`.
3. Exit behavior:
   - `0` when verification passes;
   - `1` when verification fails.
4. Markdown output includes:
   - plan dir;
   - verified flag;
   - failure count;
   - failure list.
5. JSON output via `--json` includes:
   - `plan_dir`
   - `verified`
   - `failure_count`
   - `failures`
6. Tests cover both passing Markdown output and failing JSON output.

Harness meaning:

1. Repair-plan trust is now independently checkable.
2. CI can verify control-plane artifacts before phase enforcement or repair execution.
3. Future orchestrators can compose plan generation, verification, phase gating, and execution as separate deterministic steps.
4. 9B model calls remain downstream of trust checks instead of participating in trust decisions.

Verification:

- `python -m pytest tests\unit\test_cli_eval.py -q`: `44 passed`

New task gaps:

1. Add `verify-repair-plan` to CI recipe examples.
2. Add attestation for targeted eval stubs and materialized suites.
3. Add signed attestation support.
4. Add repair execution command that requires verified plan artifacts before running.

## Latest Progress: Iteration 138 - Repair plan attestation enforcement

This iteration connects repair-plan phase enforcement to repair-plan attestation verification.

Problem:

1. Iteration 137 made repair plans tamper-evident.
2. CLI phase enforcement still trusted in-memory plan status without requiring an attested plan artifact.
3. A release-grade repair loop should not execute or approve a phase based on unaudited control-plane metadata.

Completed:

1. `metis eval repair-plan --require-executable-phase <phase-id>` now requires `--output-dir`.
2. When phase enforcement is requested, the CLI writes the repair plan and attestation artifacts.
3. The CLI runs `verify_repair_plan_attestation(output_dir)` before phase executability checks.
4. If attestation verification fails, the command returns non-zero before checking phase status.
5. Failure output distinguishes:
   - missing `--output-dir`;
   - failed repair-plan attestation;
   - blocked/non-executable phase.
6. Added CLI tests for:
   - missing output directory;
   - attestation verification failure;
   - blocked required phase with successful attestation;
   - executable required phase with successful attestation.

Harness meaning:

1. Phase enforcement now requires a verified repair-plan artifact.
2. CI and future repair executors cannot accidentally trust unaudited plan metadata.
3. The control plane blocks both dirty plan artifacts and blocked phases before model work begins.
4. This further shifts safety and sequencing away from 9B model judgment and into deterministic harness logic.

Verification:

- `python -m pytest tests\unit\test_cli_eval.py -q`: `42 passed`

New task gaps:

1. Add a dedicated `metis eval verify-repair-plan` command.
2. Add repair-plan attestation verification to future repair execution commands.
3. Add signed attestation support.
4. Add attestation for targeted eval stubs and materialized suites.

## Latest Progress: Iteration 137 - Repair plan attestation

This iteration makes repair plans tamper-evident local artifacts.

Problem:

1. Iterations 133-136 made repair plans control execution order and phase safety.
2. That means `repair-plan.json` and `repair-plan.md` are now orchestration artifacts, not just reports.
3. If a repair plan can be edited after generation without detection, a future executor or CI job may trust stale or tampered phase metadata.
4. The harness already protects eval run artifacts with run attestation; repair plans needed equivalent coverage.

Completed:

1. Added repair-plan attestation helpers:
   - `build_repair_plan_attestation()`
   - `write_repair_plan_attestation()`
   - `verify_repair_plan_attestation()`
   - `repair_plan_attestation_to_markdown()`
2. Added predicate type:
   - `https://metis.local/attestations/repair-plan/v1`
3. `write_repair_plan()` now writes:
   - `repair-plan.json`
   - `repair-plan.md`
   - `repair-plan-attestation.json`
   - `repair-plan-attestation.md`
4. Attested subjects are:
   - `repair-plan.json`
   - `repair-plan.md`
5. Attestation files are excluded from their own subject list.
6. Predicate records:
   - builder id;
   - output directory;
   - profile;
   - task count;
   - phase count;
   - hard precondition phase ids;
   - generated timestamp;
   - artifact count.
7. Verification checks:
   - required files exist;
   - statement and predicate types match;
   - subjects are present and non-duplicated;
   - subject files exist;
   - SHA256 digests match current bytes;
   - sizes match;
   - `repair-plan.json` and `repair-plan.md` are required subjects.
8. Tests verify immediate verification success and digest drift detection after tampering.

Harness meaning:

1. Repair orchestration metadata is now locally tamper-evident.
2. Phase enforcement can later require a trusted repair plan before allowing model execution.
3. The repair loop now has a stronger artifact trust chain:
   - eval run attestation;
   - comparison diagnosis;
   - repair tasks;
   - repair plan attestation.
4. This further reduces the amount of trust delegated to a 9B model or unverified local state.

Verification:

- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_run_attestation.py -q`: `60 passed`

New task gaps:

1. Add CLI command to verify repair-plan attestation directly.
2. Add repair-plan attestation verification to phase enforcement.
3. Add signed attestation support using external signing or Sigstore-compatible flow.
4. Add attestation for targeted eval stubs and materialized suites.

## Latest Progress: Iteration 136 - Repair plan CLI phase enforcement

This iteration connects repair-plan phase status to CLI enforcement.

Problem:

1. Iteration 135 made phase executability explicit in plan JSON.
2. Automation still had no CLI-level guard to reject a blocked phase.
3. A repair loop could generate the correct plan and still proceed to behavior repair while suite hygiene or artifact trust was unresolved.
4. For a 9B-oriented harness, this kind of orchestration decision must be deterministic.

Completed:

1. Added `--require-executable-phase <phase-id>` to `metis eval repair-plan`.
2. The flag can be repeated.
3. The CLI checks required phases against `phase_status_summary.executable_phases`.
4. The command returns non-zero when the required phase is:
   - absent;
   - blocked by an incomplete hard precondition;
   - otherwise not executable.
5. Failure messages include:
   - phase id;
   - current status;
   - blocked-by phase ids.
6. The command still prints/writes the repair plan before returning non-zero so CI logs keep the diagnostic artifact.
7. Added CLI tests for blocked and executable required phases.

Harness meaning:

1. Repair-plan phase metadata is now enforceable from the command line.
2. CI can fail before invoking a model on an unsafe phase.
3. Future repair executors can reuse the same enforcement semantics.
4. The harness removes another orchestration judgment from weak models.

Verification:

- `python -m pytest tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py -q`: `97 passed`

New task gaps:

1. Add a dedicated repair execution command that consumes the same phase enforcement.
2. Persist phase status changes after each repair attempt.
3. Add dashboard rendering for blocked phase chains.
4. Add attestation over repair-plan JSON and Markdown outputs.

## Latest Progress: Iteration 135 - Repair plan phase status

This iteration makes repair plans executor-ready at the phase-status level.

Problem:

1. Iteration 134 added hard precondition metadata.
2. The plan still did not say which phases were currently executable.
3. A CLI, dashboard, or future repair executor would need to reimplement precondition logic.
4. That would push orchestration judgment back into weak models or duplicated scripts.

Completed:

1. Every phase now receives:
   - `status`
   - `blocked_by`
2. Repair task status is normalized:
   - `verified` -> `verified`
   - `complete`, `completed`, `done` -> `complete`
   - `in_progress`, `running` -> `in_progress`
   - `blocked`, `failed` -> `blocked`
   - missing/unknown -> `open`
   - `not_applicable`, `skipped` -> `not_applicable`
3. Phase status is derived deterministically:
   - no tasks -> `not_applicable`
   - incomplete required hard preconditions -> `blocked`
   - all tasks complete/verified -> `complete` or `verified`
   - any running task -> `in_progress`
   - any blocked/failed task -> `blocked`
   - otherwise -> `open`
4. Plans now include `phase_status_summary`:
   - status counts;
   - blocked phases;
   - executable phases;
   - open hard preconditions.
5. Markdown rendering now displays phase status and blocked-by metadata.
6. Tests verify:
   - open suite hygiene precondition blocks downstream phases;
   - `blocked_by` identifies the blocking precondition;
   - verified preconditions unblock downstream behavior repair;
   - summary fields identify executable phases and open hard preconditions.

Harness meaning:

1. Repair plans now carry enough information for an executor to decide what can run next.
2. 9B models do not need to infer whether behavior repair is safe.
3. Precondition enforcement is now deterministic and auditable.
4. The next natural step is CLI enforcement and status persistence after repair attempts.

Verification:

- `python -m pytest tests\unit\test_eval_compare.py -q`: `57 passed`

New task gaps:

1. Add CLI enforcement that refuses to execute non-executable phases.
2. Add repair-plan phase status persistence updates after each repair attempt.
3. Add dashboard rendering for blocked phase chains.
4. Add repair-plan attestation over status and dependency metadata.

## Latest Progress: Iteration 134 - Repair plan precondition metadata

This iteration makes repair-plan preconditions machine-readable.

Problem:

1. Artifact trust and suite hygiene phases were correctly ordered.
2. Downstream tools still had to infer hard precondition semantics from phase ids and prose.
3. A reusable harness should expose execution control metadata directly.
4. 9B repair agents should not decide from natural language whether contaminated artifacts or dirty suite contracts block behavior repair.

Completed:

1. Added phase metadata:
   - `phase_type`
   - `hard_precondition`
   - `blocks`
   - `requires_completed_preconditions`
2. `phase-0-restore-artifact-trust` is now marked:
   - `phase_type: precondition`
   - `hard_precondition: true`
   - blocks comparison interpretation, model behavior repair, and targeted eval generation.
3. `phase-0b-repair-suite-hygiene` is now marked:
   - `phase_type: precondition`
   - `hard_precondition: true`
   - blocks model behavior repair, targeted eval generation, and release decision.
4. Ordinary phases are explicitly typed:
   - `phase-1-stop-release-blockers`: repair
   - `phase-2-add-targeted-evals`: verification
   - `phase-3-stabilize-owners`: stabilization
5. Added `_annotate_repair_phase_dependencies()` to derive cumulative hard-precondition dependencies from phase order.
6. Markdown rendering now shows:
   - phase type;
   - hard precondition flag;
   - required completed preconditions;
   - blocked downstream activities.
7. Unit tests verify metadata for artifact trust, suite hygiene, release blocker, and targeted eval phases.

Harness meaning:

1. Repair plans are now closer to executable control plans.
2. Dashboards and CLIs can enforce preconditions without parsing English.
3. Small models get clearer harness guardrails: first restore trustworthy inputs, then repair behavior.
4. Future phase status tracking has stable metadata to attach to.

Verification:

- `python -m pytest tests\unit\test_eval_compare.py -q`: `56 passed`

New task gaps:

1. Add CLI enforcement that refuses to execute behavior repair before hard preconditions complete.
2. Add dashboard rendering for precondition chains.
3. Add phase status fields: `open`, `in_progress`, `blocked`, `complete`, `verified`.
4. Add repair-plan attestation so phase metadata is tamper-evident.

## Latest Progress: Iteration 133 - Artifact path hygiene repair phase

This iteration moves `artifact_path_hygiene_failed` from a release reason and owner routing signal into repair-plan ordering.

Problem:

1. Iteration 132 made non-portable artifact paths a release/strict regression reason.
2. Repair plans still moved directly from artifact trust into ordinary release blockers.
3. That ordering was incomplete because invalid suite metadata is not model behavior.
4. For 9B models, mixing suite-contract hygiene with behavior repair creates unnecessary ambiguity and can cause repair attempts to optimize against a dirty contract.

Completed:

1. `build_repair_plan()` now detects repair tasks with reason `artifact_path_hygiene_failed`.
2. When present, it inserts:
   - `phase-0b-repair-suite-hygiene`
   - title: `Repair suite hygiene`
   - description: remove non-portable artifact paths and invalid eval contract metadata before repairing model behavior
3. The new phase is placed:
   - after `phase-0-restore-artifact-trust` when artifact trust tasks exist;
   - before `phase-1-stop-release-blockers` in all cases.
4. The task is still preserved in later views when applicable:
   - targeted eval phase when it has `suggested_eval`;
   - owner stabilization phase when medium/low priority;
   - `eval-suite-hygiene` owner summary.
5. Added `_is_artifact_path_hygiene_task()` as the explicit classifier for this repair-plan precondition.
6. Added focused unit tests proving:
   - suite hygiene phase precedes release blockers;
   - hygiene task ids enter the new phase;
   - behavior regressions remain in release blockers;
   - artifact trust remains before suite hygiene when both exist.
7. Added iteration documentation and updated the 9B eval report.

Harness meaning:

1. Repair planning now reflects causal order: artifact trust -> suite hygiene -> model behavior.
2. Non-portable path metadata is treated as a dirty-contract precondition rather than an ordinary model failure.
3. Small models receive a cleaner repair surface because the harness removes invalid eval metadata before asking them to reason about behavior.
4. Metis moves closer to a reusable harness base where scenario-specific artifacts can vary, but contract hygiene remains universal.

Verification:

- `python -m pytest tests\unit\test_eval_compare.py -q`: `56 passed`

New task gaps:

1. Add configurable severity thresholds for artifact path hygiene diagnostics.
2. Add dashboard rendering for `phase-0b-repair-suite-hygiene`.
3. Add repair-plan export metadata that marks pre-behavior phases as hard preconditions.
4. Add run-to-run trend comparison of artifact path diagnostics.
5. Add real small-model eval cases that intentionally produce path hygiene failures.

## Latest Progress: Iteration 132 - Artifact path hygiene release gate

This iteration upgrades artifact path diagnostics from observability metadata to a release/strict regression reason.

Completed:

1. Added regression reason:
   - `artifact_path_hygiene_failed`
2. Release and strict profiles now emit this reason when:
   - `artifact_path_diagnostic_summary.total > 0`
3. Regression reason links now carry:
   - `artifact_path_diagnostics`
   - `artifact_path_diagnostic_summary`
   - linked task ids
   - failure artifacts
   - timelines
4. Comparison Markdown now renders the compact diagnostic summary in reason links.
5. Repair task routing now maps this reason to:
   - owner area: `eval-suite-hygiene`
   - explicit action to remove non-portable artifact paths
   - suggested suite hygiene regression eval
6. Tests verify:
   - reason emission;
   - reason link summary;
   - Markdown output;
   - repair task owner/action/eval routing.

Harness meaning:

1. Non-portable artifact metadata now blocks release instead of being advisory.
2. CI can gate on artifact contract hygiene.
3. Repair planning separates suite hygiene from model behavior and generic quality gate failures.
4. The harness is safer for multi-machine use and scenario-specific agent development.

Verification:

- `python -m pytest tests\unit\test_eval_compare.py -q`: `54 passed`
- `python -m compileall -q metis`: passed

New task gaps:

1. Make artifact path hygiene severity thresholds configurable.
2. Add dashboard rendering for `artifact_path_hygiene_failed`.
3. Add run-to-run trend diff for artifact path diagnostics.
4. Add real small-model suites that exercise path hygiene failure and repair.

## Latest Progress: Iteration 131 - Compare artifact path diagnostic summary

This iteration moves artifact path diagnostic aggregation into `eval compare`.

Completed:

1. `compare_eval_runs()` now derives artifact path diagnostics from `quality_gate_diff.new_failed_gates`.
2. Comparison JSON now includes:
   - `artifact_path_diagnostics`
   - `artifact_path_diagnostic_summary`
3. `quality_gate_failed` regression reason links now include:
   - `artifact_path_diagnostics`
   - `artifact_path_diagnostic_summary`
4. Comparison Markdown now renders:
   - artifact path diagnostic summary;
   - artifact path diagnostic details;
   - compact reason-link summary for `quality_gate_failed`.
5. Tests verify compare-level summary values and Markdown output.

Harness meaning:

1. Artifact path contract hygiene is visible at compare time, before targeted eval stubs are generated.
2. CI and release tooling can inspect one comparison JSON file for both gate drift and path hygiene.
3. Compare reports, generated stubs, and materialized suites now share the same diagnostic vocabulary.

Verification:

- `python -m pytest tests\unit\test_eval_compare.py -q`: `54 passed`
- `python -m compileall -q metis`: passed

New task gaps:

1. Add release-gate thresholds for artifact path diagnostics.
2. Add dashboard rendering for compare-level diagnostic summaries.
3. Add trend comparison for artifact diagnostic summaries across baseline/current runs.
4. Signed artifact bundle attestation remains needed.

## Latest Progress: Iteration 130 - Artifact path diagnostic summary

This iteration adds aggregated summary counts for filtered artifact path diagnostics.

Completed:

1. Generated targeted eval stubs now include top-level `artifact_path_diagnostic_summary`.
2. Materialized targeted suites preserve the same summary.
3. Summary fields:
   - `total`
   - `by_reason`
   - `by_source`
   - `by_gate`
   - `by_task`
4. Stub Markdown and suite Markdown now render the summary.
5. Per-task `artifact_path_diagnostics` remain unchanged for audit details.
6. `suite-schema-v1.json`, `suite-schema.md`, and `9b-eval-report.md` now document the summary field.
7. Tests verify:
   - total diagnostic count;
   - reason counts;
   - source counts;
   - gate counts;
   - task counts;
   - preservation through materialized suite generation;
   - Markdown rendering.

Harness meaning:

1. Dashboards no longer need to scan every task to show artifact path hygiene.
2. Release reports can show whether bad metadata paths are increasing by reason.
3. The harness now has both detailed diagnostics and aggregate observability for artifact contract generation.

Verification:

- `python -m pytest tests\unit\test_eval_compare.py -q`: `53 passed`
- `python -m compileall -q metis`: passed

New task gaps:

1. Compare report generation should link artifact path diagnostic summaries to regression reason links.
2. Dashboard rendering should expose reason/source/gate trend views.
3. Real small-model eval suites should exercise artifact diagnostic summary cases.
4. Signed artifact bundle attestation remains needed.

## Latest Progress: Iteration 129 - Filtered artifact path diagnostics

This iteration turns non-portable artifact path filtering into auditable diagnostic metadata.

Completed:

1. Targeted eval stubs now include `artifact_path_diagnostics`.
2. Materialized targeted suite tasks preserve `artifact_path_diagnostics`.
3. Stub Markdown and materialized suite Markdown render artifact path diagnostics.
4. Diagnostics are collected from:
   - `path`
   - `artifact_path`
   - `expected_artifact`
   - `paths`
   - `artifact_paths`
   - `expected_artifacts`
   - `missing_artifact_paths`
   - `requirement_criteria[*].required_artifact_path`
   - `requirement_criteria[*].artifact_path`
5. Each diagnostic records:
   - task id
   - gate
   - source field
   - original path
   - rejection reason
   - criterion id when available
6. Current rejection reasons:
   - `not_relative`
   - `windows_drive_prefix`
   - `parent_traversal`
7. `suite-schema-v1.json` and `suite-schema.md` now document the wrapper metadata field.
8. Tests verify diagnostics survive stub generation, materialized suite generation, and Markdown rendering.

Harness meaning:

1. Filtering is no longer silent.
2. Dashboards can explain why a runtime artifact path was not compiled into the executable eval contract.
3. Reviewers can distinguish contract hygiene from model failure.
4. This improves the traceability layer needed for a reusable harness that will support many scenario-specific agents.

Verification:

- `python -m pytest tests\unit\test_eval_compare.py -q`: `53 passed`
- `python -m compileall -q metis`: passed

New task gaps:

1. Compare summary should count filtered artifact paths by reason.
2. Dashboard should group artifact diagnostics by source and reason.
3. Real small-model eval suites should include bad-metadata diagnostic cases.
4. Signed attestation remains needed.

## Latest Progress: Iteration 128 - Targeted eval artifact path filter

This iteration aligns targeted eval generation with the artifact path policy added in Iteration 127.

Completed:

1. `build_eval_stubs_from_repair_tasks()` now filters artifact paths extracted from quality gate metadata before compiling executable eval contracts.
2. `_quality_gate_expected_artifacts()` now keeps only portable relative artifact paths.
3. `_quality_gate_requirement_criteria()` now filters:
   - `missing_artifact_paths`
   - `requirement_criteria[*].required_artifact_path`
   - `requirement_criteria[*].artifact_path`
4. Non-portable raw criterion artifact fields are removed before the criterion is added to a generated eval.
5. If removing a non-portable artifact field leaves no verifier field, the criterion is skipped.
6. Added tests proving:
   - valid `outputs/report.md` survives;
   - `../escape.md`, `/tmp/report.md`, and `C:\tmp\report.md` do not enter `expected_artifacts` or `requirement_criteria`;
   - unrelated valid tool criteria still survive.

Harness meaning:

1. Runtime quality gate metadata can preserve local observed paths for diagnosis.
2. Generated repair suites only contain portable executable artifact contracts.
3. Suite generation and suite validation now enforce the same artifact path policy.
4. This prevents a repair suite generated on one machine from failing immediately on another machine due to local absolute paths.

Verification:

- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_eval_suite_validation.py -q`: `71 passed`
- `python -m compileall -q metis`: passed

New task gaps:

1. Add explicit diagnostic metadata for filtered non-portable artifact paths.
2. Compare/dashboard should group artifact path policy issues separately from model failures.
3. Real small-model suites should include portable artifact-only criteria.
4. Signed attestation remains needed for artifact bundle trust.

## Latest Progress: Iteration 127 - Portable artifact path validation

This iteration adds path-policy validation for artifact contracts.

Completed:

1. `validate_eval_suite()` now checks artifact paths in:
   - `expected_artifacts`
   - `requirement_criteria[*].required_artifact_path`
   - `requirement_criteria[*].artifact_path`
2. Artifact contract paths must be portable relative paths.
3. The validator rejects:
   - absolute POSIX paths;
   - home-relative paths beginning with `~`;
   - Windows drive-prefixed paths;
   - parent traversal segments.
4. New validation code:
   - `invalid_artifact_path`
5. Tests now cover invalid `expected_artifacts`, invalid `required_artifact_path`, and invalid `artifact_path`.
6. Documentation now states that artifact paths in suite contracts must be portable relative paths.

Harness meaning:

1. Eval suites remain portable across machines and CI.
2. Targeted repair contracts cannot silently bake in one local workspace path.
3. Artifact requirements are constrained to the intended suite/workspace boundary.
4. This makes scenario-specific agents safer to build on the same Metis base.

Verification:

- `python -m pytest tests\unit\test_eval_suite_validation.py -q`: `18 passed`
- `python -m compileall -q metis`: passed

New task gaps:

1. Targeted eval generation should normalize or reject non-portable artifact paths extracted from quality gate metadata.
2. Compare/dashboard should distinguish artifact path policy failures from model output failures.
3. Signed attestation is still needed for tamper-evident artifact bundles.
4. Real small-model suites should include artifact-only criteria with portable paths.

## Latest Progress: Iteration 126 - Requirement criteria validation and repair propagation

This iteration turns the artifact/tool criterion work from runtime-only verification into a stronger contract loop.

Completed:

1. `requirements_covered` now supports structured criteria without text when they declare at least one verifier field.
2. Tool-only criteria are now valid:
   - `{"id": "REQ-tool", "required_tool": "write_file"}`
3. Artifact-only criteria are now valid:
   - `{"id": "REQ-artifact", "required_artifact_path": "outputs/report.md"}`
4. `validate_eval_suite()` now performs deeper `requirement_criteria` validation:
   - every entry must be an object;
   - present string fields must be non-empty strings;
   - every criterion must declare at least one verifier field;
   - `required_tool` / `tool_name` must refer to a known tool when a tool registry is supplied.
5. New validation failure classes:
   - `empty_requirement_criterion`
   - `invalid_type`
   - `unknown_tool`
6. `build_eval_stubs_from_repair_tasks()` now compiles quality gate metadata into executable criteria:
   - `missing_artifact_paths` -> `required_artifact_path`
   - `missing_tools` -> `required_tool`
7. Targeted suites preserve the generated artifact/tool requirement criteria.
8. Tests now cover:
   - tool-only gate criteria;
   - malformed/empty/unknown-tool suite criteria;
   - compare-to-targeted-eval propagation for missing artifact paths and tools.

Harness meaning:

1. Contract mistakes are caught before provider calls.
2. Runtime artifact/tool gaps become machine-readable repair eval contracts.
3. The repair loop no longer depends on prose to remember that a file or tool trajectory was missing.
4. Metis is closer to a reusable scenario-agnostic harness where the domain changes but the verification grammar remains stable.

Verification:

- `python -m pytest tests\unit\test_quality_gates.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_compare.py -q`: `77 passed`
- `python -m compileall -q metis`: passed

New task gaps:

1. Compare output should aggregate requirement gaps by requirement id, artifact path, and tool name.
2. Dashboard should show requirement gap classes: text, evidence, artifact, tool.
3. Suite validation should add portable artifact path policy checks.
4. Real small-model eval suites should include artifact-only and tool-only criteria.
5. Attestation should become signed, not only hash-based.

## Latest Progress: Iteration 125 - Requirement artifact and tool criteria

This iteration extends structured requirement verification from evidence-only acceptance criteria into artifact and trajectory acceptance criteria.

Completed:

1. `requirements_covered_gate()` now reads `tool_results` from quality gate context.
2. `requirement_criteria` now supports:
   - `required_artifact_path`
   - `artifact_path` alias
   - `required_tool`
   - `tool_name` alias
3. Artifact verification normalizes path separators, so a suite can declare `outputs/report.md` and match a Windows runtime artifact path such as `...\outputs\report.md`.
4. Tool verification requires a successful tool result. A failed result for the same tool does not satisfy the criterion.
5. Failure metadata now includes:
   - `missing_artifact_paths`
   - `missing_tools`
6. Successful metadata now includes those fields as empty arrays for stable downstream parsing.
7. Unit tests cover a requirement that has text coverage and artifact coverage but fails until the required `write_file` tool result is present.
8. Runner tests confirm structured criteria metadata continues to flow through quality gate execution.
9. Eval schema documentation now describes artifact/tool criteria fields and aliases.
10. The 9B eval report now documents that requirement criteria bind to observed artifacts and successful tools, not only final text.

Harness meaning:

1. The verifier can now prove that a deliverable exists in the artifact record.
2. The verifier can now prove that a named tool action actually completed successfully.
3. Small models cannot satisfy a delivery requirement only by claiming completion in prose.
4. Repair tasks can distinguish missing content, missing evidence, missing artifacts, and missing tool trajectory.
5. This is a necessary base capability for a reusable scenario-agnostic agent harness, because every future vertical agent will need scenario-specific artifacts and tool workflows while reusing the same verification contract.

Verification:

- `python -m pytest tests\unit\test_quality_gates.py tests\unit\test_eval_runner.py -q`: `48 passed`
- `python -m pytest tests\unit\test_quality_gates.py tests\unit\test_eval_runner.py tests\unit\test_eval_compare.py tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q`: `137 passed`
- `python -m compileall -q metis`: passed

New task gaps:

1. Suite validation should validate `required_artifact_path` and `required_tool` references before execution.
2. Targeted eval generation should compile `missing_artifact_paths` and `missing_tools` from quality gate metadata into explicit `requirement_criteria`.
3. Compare output should aggregate requirement id, missing artifact path, and missing tool trends.
4. Dashboards should show requirement gap type: text/evidence gap, artifact gap, or trajectory/tool gap.
5. Artifact evidence still needs cryptographic signing beyond local hash attestation.
