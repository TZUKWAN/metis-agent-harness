# Iteration 069: Run Manifest Summary

日期：2026-05-25

## 本轮目标

Iteration 067/068 已经把 schema repair hint recovery 做进 eval report 和 release gate。但 run manifest 与 latest pointer 仍只包含 success rate、task count 等基础字段。

这会让外部 dashboard、latest pointer、run comparison automation 需要额外打开 `eval-report.json` 才能读取关键 summary。本轮把 suite summary 写入 manifest 和 latest pointer，让 eval run 的入口文件直接携带关键指标。

## 已完成变更

1. Generic eval suite manifest 新增：

- `summary`

2. Generic latest pointer 新增：

- `summary`

3. Real small-model eval manifest 新增：

- `summary`

4. Real small-model latest pointer 新增：

- `summary`

5. 这四处都复用 `EvalSuiteResult.summary`，避免 manifest、pointer 和 eval-report.json 之间计算逻辑分叉。

## 新增测试覆盖

1. generic eval writer 会把 hint recovery summary 写入 `manifest.json`。
2. generic eval writer 会把 summary 写入 `latest.json`。
3. `generic_eval_suite_manifest` 单独调用时包含 summary。
4. real small-model writer 会把 hint recovery summary 写入 `manifest.json`。
5. real small-model writer 会把 summary 写入 `latest.json`。
6. auto run name 路径下也保留 summary。

## 对 Metis Harness 的意义

生产级 agent harness 的 eval 产物必须便于机器消费。`manifest.json` 和 `latest.json` 是最容易被外部工具读取的入口：

1. dashboard 不需要解析完整 report。
2. CI 可以快速读取 summary 指标。
3. latest pointer 可以直接暴露当前模型/profile 的关键健康度。
4. 后续 comparison 可以优先从 manifest 读取 summary。

这一步让 schema repair hint recovery 从 report 内部指标变成 run 级元数据。

## 当前限制

1. comparison report 还没有比较 summary delta。
2. latest pointer 只有最新 run，没有保留上一轮 baseline summary。
3. manifest 没有压缩或拆分，summary 变大后需要控制字段体积。
4. dashboard schema 还没有正式定义。

## 下一步任务

1. comparison report 增加 hint recovery rate delta。
2. comparison report 增加 hint type failure regression。
3. 定义 eval run manifest schema version。
4. real small-model eval suite 加入 hint recovery tasks。

## 验证结果

- `python -m pytest tests\unit\test_eval_suite_run.py tests\e2e\test_local_9b_eval.py -q`
  - 结果：13 passed, 3 skipped
- `python -m compileall -q metis`
  - 结果：通过

