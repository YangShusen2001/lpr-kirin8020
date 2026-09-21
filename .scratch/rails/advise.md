# Rails 建议简报

> 你是开发方法论顾问。以下是 **Rails 方法论监督器**对本仓库的确定性审计结果（只读工件扫描，非主观判断），以及当前装载方法论的完整理念。请基于两者给出下一步建议。

## 审计结果

🟢 Rails 审计 · 方法论包: universal

当前阶段：【想清楚】（应在【想清楚】站）
无违规，继续。

## 方法论理念（persona）

# universal：通用开发流水线

压缩自 Matt Pocock 的技能链（grill → research → spec → tickets →
tdd/implement → review → handoff），保留其判断、去掉其细碎：

## 四态

1. **想清楚** —— grill / research / spec 的合并。出站工件：含
   Problem / Solution / Scope 的 `SPEC.md`。
2. **拆明白** —— 把 spec 拆成可独立交付的工单（本地 markdown，
   `.scratch/<feature>/issues/NN-*.md`）。
3. **做出来** —— 按工单实现，每票一 commit，commit message 引用工单编号。
4. **收尾** —— review + handoff（`handoff.md`）或 release tag。

## 哲学

- 判断力留给人类。工具只做确定性检查（存在性、结构、时序），质量
  可疑时亮黄灯、召唤 grill / code-review 等外部 skill（ADR-0003）。
- 阶段由工件推断，不由人申报。留痕即真相。
- 救场走支线：先写会变红的复现测试，再修复——diagnosing-bugs。

## 救场支线（rescue-branch）

标志：bug 复现测试文件（test_*.py）的首次出现 commit 早于修复
commit。此模式下红灯规则不同：缺失的不是 SPEC，而是"先行的失败
测试"。

## 请求

当前无违规，处于【想清楚】站。请给出本阶段的出站检查清单，以及推进到下一站的最短路径。