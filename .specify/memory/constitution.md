<!--
Sync Impact Report:
- Version change: 1.0 → 1.1.0
- Modified principles:
  - II. 模块化分层 (更新目录结构反映重构)
- Added sections: 无
- Removed sections: 无
- Templates status:
  - .specify/templates/plan-template.md: ✅ 无需更新
  - .specify/templates/spec-template.md: ✅ 无需更新
  - .specify/templates/tasks-template.md: ✅ 无需更新
- Follow-up TODOs: 无
-->

# SpectraViewer Constitution

**项目定位**: 光子器件测试数据处理程序，用于读取测试数据进行绘图和简要分析

---

## Core Principles

### I. 数据完整性优先

- **原则**: 原始数据不可修改，所有处理均为只读操作
- **实施**:
  - CSV 读取后保留原始波长和功率数据
  - 插值、减法等操作生成新数组，不覆盖原数据
  - SpectraManager 中 data 字典存储原始数据，get_xy() 返回副本

### II. 模块化分层

- **原则**: 数据处理与 GUI 严格分离
- **分层结构**:
  ```
  core/              → 纯数据处理层 (无 GUI 依赖)
    ├── io.py        → CSV 读取
    ├── manager.py   → SpectraManager
    ├── grid.py      → 网格/插值工具
    └── utils.py     → 通用工具

  analysis/          → 光子学分析层 (无 GUI 依赖)
    ├── ring.py      → 微环谐振器分析
    ├── peak.py      → 峰值/谷值检测
    └── fitting.py   → 洛伦兹拟合

  visualization/     → 可视化层 (仅 matplotlib)
    └── plotter.py   → 出版质量绑图

  gui/               → GUI 交互层 (PyQt5)
    ├── main_window.py → 主窗口
    └── widgets.py     → 通用组件

  main.py            → 入口配置
  ```
- **边界规则**:
  - `core/` 禁止导入 PyQt5
  - `analysis/` 禁止导入 PyQt5
  - `visualization/` 禁止导入 PyQt5
  - 分析逻辑与绘图逻辑分离

### III. 科学计算可复现

- **原则**: 任何分析结果必须可复现
- **要求**:
  - 关键参数使用默认值，但允许用户覆盖
  - 分析函数返回完整结果对象，不仅是图像
  - 随机种子固定 (如需随机算法)
  - 拟合参数、阈值等记录在结果中

### IV. 中文用户界面

- **原则**: 界面语言为简体中文
- **范围**:
  - GUI 标签、按钮、提示
  - 日志输出
  - 错误消息
  - 图像标题和标签 (可切换英文用于出版)

### V. 增量功能开发

- **原则**: 新功能以插件形式添加，不破坏现有功能
- **扩展点**:
  - 新分析类型 → 在 `analysis/` 添加新模块
  - 新文件格式 → 扩展 `core/io.py`
  - 新绘图样式 → 扩展 `visualization/plotter.py`
  - 新 GUI 面板 → 在 `gui/` 添加新模块

---

## 技术约束

### 依赖管理

- **核心依赖**: numpy, scipy, pandas, matplotlib, PyQt5
- **版本策略**: 兼容主流版本，不锁定具体版本号
- **新增依赖**: 仅在必要时添加，需说明用途

### 文件格式

- **输入**: SANTEC CSV (14行头 + 数据列)
- **输出**:
  - 图像: PNG/PDF (matplotlib 保存)
  - 数据: 暂无导出功能 (未来可添加)

### 性能考虑

- **数据量**: 典型单文件 < 100,000 点
- **批量加载**: 支持文件夹内 10-100 个文件
- **响应要求**: 绘图 < 1 秒，分析 < 5 秒

---

## 开发规范

### 代码风格

- 函数文档使用中文或中英双语
- 变量名使用英文，遵循 snake_case
- 常量使用大写 SNAKE_CASE

### 错误处理

- 文件读取失败 → 打印错误，跳过该文件，继续处理其他文件
- 参数无效 → 打印提示，不执行操作
- 分析失败 → 打印详细错误信息，不崩溃

### 测试策略

- 当前阶段: 无正式测试框架
- 验证方式: 使用实际数据手动验证
- 未来: 可添加 pytest 单元测试

---

## Governance

### 优先级

1. 数据准确性 > 性能 > 界面美观
2. 用户需求 > 代码整洁度
3. 功能完整 > 过度工程

### 变更审批

- 新功能: 需明确需求和预期行为
- API 变更: 需说明向后兼容性
- 架构变更: 需讨论并记录决策

---

**Version**: 1.1.0 | **Ratified**: 2026-04-06 | **Last Amended**: 2026-04-06
