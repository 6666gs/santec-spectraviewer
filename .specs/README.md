# SpectraViewer Specifications

本目录包含项目的规格文档，用于帮助 AI 更好理解项目结构。

## 文件索引

| 文件 | 描述 |
|------|------|
| [spectra-lib.md](spectra-lib.md) | 核心数据处理库：CSV 读取、SpectraManager、绘图 |
| [Ring-analyse.md](Ring-analyse.md) | 微环谐振器分析：FSR 计算、Q 因子拟合 |
| [app-gui.md](app-gui.md) | PyQt5 GUI：窗口布局、事件处理、公式引擎 |
| [file-naming.md](file-naming.md) | SANTEC CSV 文件命名规范与解析规则 |

## 使用方式

当你需要 AI 帮你修改项目时，可以：

```
请参考 .specs/ 目录中的规格，帮我实现 XXX 功能
```

AI 会根据规格文档理解项目结构，生成符合现有模式的代码。

## 规格维护

当项目发生重大变更时，请同步更新对应的规格文档。
