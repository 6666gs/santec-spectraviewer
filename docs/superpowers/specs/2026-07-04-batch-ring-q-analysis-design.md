# 批量微环 Q 分析设计（多 FSR 自动分离）

## 概述

新增一个**独立命令行程序**，专门批量分析微环直通端（through port）透射谱，提取每个谐振峰的负载 Q（Ql）与本征 Q（Qi），并输出每个文件的 Q 统计分布图。核心新增能力：**自动识别一个谱中共存的多种模式（不同 FSR），并对每个模式单独给出 Q 统计**。

处理粒度：**单文件 = 单微环**，逐个文件独立处理，结果按输入文件名命名，**不做跨文件汇总**。

## 目标（需求映射）

1. 输入为项目内已定义的 `loss` 或 `raw` 数据（raw 需指定 reference），也支持**简单两列**（波长, 损耗 dB）。
2. 自动识别各参数（数据类型、表头行数、量程、通道等），复用现有 `core/io.py`。
3. 指定目标目录，自动输出分析结果为图片（Q 值统计分布）。
4. **新算法**：自动处理一个谱中多种 FSR 共存的情况，识别不同 FSR 的峰族，分模式给出 Q 统计。
5. 默认只处理直通端；下载端（drop port）本期不处理。

## 非目标（YAGNI）

- 不做跨文件/跨器件的汇总统计（用户明确：单微环单微环处理，按文件名出结果）。
- 不处理下载端 add-drop 联合建模。
- 不新增 GUI；不改动现有 PyQt5 界面。
- 不追求在线交互；一次性批处理出图 + CSV。

## 方案选择

**多 FSR 分离算法：方案 A —— 频域贪心梳状提取（RANSAC 式）**（已采纳）

| 方案 | 思路 | 取舍 |
|------|------|------|
| **A. 频域贪心梳状提取** ✅ | 频率域中，每个模式族是近似等间隔梳齿。用"多近邻两两间距分布"播种候选 FSR；对候选从种子对向两侧延伸成链，允许 FSR 缓慢漂移（色散）与跳过缺齿；取走已用峰后对残余重复；族长不足即停 → 自动确定模式数 K | 纯 numpy/scipy；天然处理交错、色散、缺齿；K=1 时退化为单模，复现旧行为 |
| B. 特征聚类（间距+线宽+深度） | 逐峰特征做 GMM/KMeans | 需 sklearn（非现依赖）；交错时"局部间距"定义不清；模式线宽可能相近 → 不稳 |
| C. 傅里叶/自相关周期检测 | 对峰梳做 FFT/自相关找周期 | 谐波易被误当作独立 FSR；仍需 A 的逐峰指派步骤。仅作为 A 的候选 FSR 播种手段 |

采用 A，并借用 C 的思想（间距分布）来播种候选 FSR。理由：满足"全自动、FSR 未知、可能交错"的要求，无新依赖，且按族做拟合窗口比现有 `cal_Q` 的全局近邻窗口更准。

**为何在频率域做分离**：给定模式的 FSR 在频率上近似恒定（波长上随色散变化更明显）。现有 `Ring` 已计算 `fre`（THz），直接复用。

---

## 架构与分层

遵循项目分层：`core/`、`analysis/` 不依赖 PyQt5；可视化在 `visualization/`。

```
batch_ring_q.py                 # 新增：CLI 入口
analysis/multimode.py           # 新增：多模式分离 + 分模式 Q 分析（纯 numpy/scipy）
visualization/ring_report.py    # 新增：单文件多模式报告图（仅 matplotlib）
core/io.py                      # 改动：新增自动表头行数探测，支持简单两列文件
analysis/fitting.py             # 复用：fit_lorentzian_peak（按族窗口逐峰拟合）
```

### 数据流

```
CLI(INPUT_DIR, --out, --type, --reference, ...)
  └─ 发现文件 (glob)
      └─ 对每个文件:
          ├─ load_spectrum() → (lam_nm, loss_db)     # core/io + 自动 skiprows
          ├─ analyze_multimode(lam, loss_db, params) # analysis/multimode
          │     ├─ detect_resonances()  → 谷索引
          │     ├─ separate_modes()     → list[ModeFamily]   ★核心新算法
          │     └─ 逐族逐峰 fit_lorentzian_peak() → list[ResonanceFit]
          ├─ plot_multimode_report(result) → Figure  # visualization/ring_report
          │     └─ 保存 <stem>_Qdist.png
          └─ 写 <stem>_results.csv + 控制台日志
```

---

## 核心算法：`analysis/multimode.py`

### 数据结构（不可变优先）

```python
@dataclass(frozen=True)
class ModeFamily:
    label: str            # "Mode 1"（按 FSR 升序编号）
    peak_indices: np.ndarray   # 指向 lam/T 网格的整型索引，已按波长排序
    fsr_nm: float
    fsr_thz: float

@dataclass(frozen=True)
class ResonanceFit:
    mode: str             # 所属 ModeFamily.label
    lambda0_nm: float
    ql: float
    qi: float
    er: float             # 消光比（线性 0-1，拟合直接给出）
    gamma_pm: float       # 3dB 全宽 (pm)
    r_squared: float
    fsr_nm: float         # 该峰所属族的本地 FSR

@dataclass(frozen=True)
class MultiModeResult:
    source_name: str
    lam: np.ndarray       # 分析用统一网格波长 (nm)
    t_db: np.ndarray      # 对应透射 (dB)
    families: tuple[ModeFamily, ...]
    fits: tuple[ResonanceFit, ...]
    unassigned_idx: np.ndarray   # 未归入任何模式的谷索引
```

### `detect_resonances(lam, t_db, *, prominence=None, min_distance=None, height=None)`

- 复用 `core.grid.sanitize_xy` 清洗；插值到均匀波长网格（`create_uniform_grid` + `interp_on_grid`，步长由数据推断），保证 `find_peaks` 的 `distance` 语义一致。
- `detect_signal = -t_db`（直通端谐振是谷）。
- 参数默认：`prominence = max(0.5, ptp(detect_signal) * 0.05)`；`distance` 取**较小值**（约 0.2×粗中位间距或几点），以免把交错的跨模式谷合并——跨模式最小间距小于单模 FSR，故靠 prominence 抑噪而非靠大 distance。
- 返回：`(lam_grid, t_grid, dip_idx)`。

### `separate_modes(fre_thz, dip_idx, *, max_modes=None)` ★

在**频率域**操作（`f = c/(lam*1e-9)/1e12`，升序排列谐振频率 `f_1<...<f_N`）。命名常量：`K_NEIGH=6`、`MATCH_TOL=0.25`、`MIN_FAMILY=3`、`MAX_SKIP=1`。

1. **候选 FSR 播种**：对所有满足 `1 ≤ j-i ≤ K_NEIGH` 的峰对，收集差值 `d = f_j - f_i`；对 `d` 做核密度/直方图，取密度峰作为候选 FSR 列表（按支持峰对数排序）；合并容差内的近重复候选。
   - 说明：交错梳中同族相邻齿间会夹入他族齿，故最近邻差不等于 FSR；需看到第 2~K 近邻的差，FSR 才作为强复现间距浮现。
2. **贪心链提取**（循环，直到未用峰 < `MIN_FAMILY` 或无候选可成链）：
   - 取当前最强候选 `FSR0`，在未用峰中找种子（存在间距 ≈ `FSR0` 的邻峰）。
   - 双向延伸：从链端 `f_e` 预测下一齿 `f_e ± FSR_local`，在未用峰中找容差 `MATCH_TOL·FSR_local` 内最近峰；命中则加入并更新 `FSR_local`（本地相邻差，允许色散漂移）；未命中则尝试跳过一齿 `f_e ± 2·FSR_local`（至多 `MAX_SKIP` 次）；再不中则停。
   - 链长 ≥ `MIN_FAMILY` 则接受为一个族并标记已用；否则丢弃该候选。
   - 在残余未用峰上重算候选 FSR，继续。
   - `max_modes` 非空时，达到上限即停。
3. **收尾**：可将残余未用峰吸收进某族（落在其预测齿位容差内）；其余记为 `unassigned`。
4. **编号**：按 FSR 升序命名 `Mode 1..K`（K=1 即单模）。

### `analyze_multimode(lam, t_db, *, min_r2=0.9, **detect_kw)`

- `detect_resonances` → `separate_modes` → 逐族逐峰拟合。
- **按族窗口**：族内成员按波长排序，每峰窗口取到**同族**左右邻峰的中点（推广现有 `Ring.cal_Q` 的 `fit_window_by_neighbors`，但邻居限定同族 → 间距正确、窗口不跨他族峰）。
- 逐峰 `fit_lorentzian_peak(lam_slice, t_slice_db, fsr_nm_local)`；`R² < min_r2` 的峰剔除并计入日志。
- 组装并返回 `MultiModeResult`。

---

## 输入处理

### `core/io.py` 改动：自动表头行数

新增 `detect_header_rows(path) -> int`：扫描文件，返回首个"能解析出 ≥2 个数值、且其后若干行同样为数值"的行号作为 `skiprows`。兼容：

- SANTEC 标准文件（约 14 行头）；
- 无头简单两列（波长, 损耗 dB）。

CLI 的加载封装 `load_spectrum(path, data_type, reference, channel)`：先 `detect_header_rows` 得 `skiprows`，再调用现有 `read_santec_csv(path, data_type, reference_path, skiprows)`，复用 loss/raw 判别、多量程拼接、reference 相减逻辑。

- 简单两列：`read_santec_csv` 的列探测回退为单数据列 → `loss`；文件名无 `loss/raw` 时 `auto` 判为 `loss`。✅
- 多通道：默认取返回结果的**第一通道**；`--channel CHx` 指定。直通端为默认对象。

---

## 输出（`visualization/ring_report.py` + CLI）

每个输入文件产出一套，落在 `--out` 目录，按输入文件名（stem）命名：

### `<stem>_Qdist.png` —— 单张综合图

复用期刊风格（`_JC` 配色、刻度向内、无网格、白底）。多模式用一小组定性配色区分。布局（约 2 行）：

- **顶部（通栏）**：全谱 `T(dB) vs λ`（黑 0.8pt），各模式谐振谷用不同颜色标记；图例 `Mode k (FSR=x.xx nm, N=n)`；`unassigned` 用灰色空心标记。
- **下排**：
  - Ql 分布：每模式着色；每模式 N≥8 时用直方图，否则用 `Ql vs λ` 散点（避免稀疏直方图误导）。
  - Qi 分布：同上。
  - 小结表：每模式一行 `Mode / FSR(nm) / N / Ql(中位±std) / Qi(中位±std)`。

### `<stem>_results.csv`

每谐振峰一行：`mode_id, fsr_nm, lambda0_nm, ql, qi, er_db, gamma_pm, r_squared`。

其中 `er_db` 为谐振谷深度（dB，正值），由线性消光比换算：`er_db = -10*log10(max(1 - er, 1e-6))`。

### 控制台日志（每文件）

```
[文件名] type=loss, ch=CH1, 谷=37
  识别到 2 个模式:
    Mode 1: FSR=8.12 nm, N=18, Ql(中位)=1.2e5, Qi(中位)=2.4e5
    Mode 2: FSR=12.05 nm, N=13, Ql(中位)=9.8e4, Qi(中位)=1.9e5
  剔除 R²<0.9: 3 个; unassigned: 3 个
```

---

## CLI 接口 `batch_ring_q.py`

```
python batch_ring_q.py INPUT_DIR [选项]
  --out DIR           输出目录（默认 INPUT_DIR/ring_q_results）
  --type {auto,loss,raw}   数据类型（默认 auto）
  --reference PATH    raw 模式的参考文件
  --pattern GLOB      文件名匹配（默认 *.csv）
  --channel CHx       指定通道（默认第一通道）
  --min-r2 FLOAT      拟合 R² 阈值（默认 0.9）
  --max-modes INT     模式数上限（默认不限）
  --prominence / --distance / --height   寻峰参数（可选，默认自动）
```

- 逐文件 try/except，单个失败打印错误并继续，不中断整批。
- 结束打印总计：成功/失败文件数、总谐振峰数。

---

## 健壮性 / 边界

- 单模谱 → K=1，正常出一模式结果；复现旧单模行为。
- 谷太少（< `MIN_FAMILY`）无法成梳 → 全部 unassigned，日志告警，不崩。
- 拟合失败或 `R² < min_r2` → 剔除并计数。
- 非均匀采样的简单两列 → 插值到均匀网格后再检测。
- 沿用 Q 汇总的 4σ 离群过滤（用于图中统计与小结表）。

---

## 测试（pytest）

项目原无测试框架，本期引入 pytest（符合 Python 测试规则），置于 `tests/`。

- `tests/test_multimode.py`：
  - 合成两把已知 FSR 的**交错**梳 + 已知洛伦兹 Q，验证 `separate_modes` 正确分成 2 族、FSR 与真值误差 < 容差；`analyze_multimode` 提取的 Ql/Qi 与真值在容差内。
  - 单模（K=1）用例。
  - 缺齿（删若干峰）用例：验证跳齿延伸仍成链。
  - 含噪/假峰用例：验证假峰落入 unassigned，不污染族。
- `tests/test_io_header.py`：`detect_header_rows` 对 14 行头与无头两列文件均返回正确值。

---

## 涉及文件

| 文件 | 改动 |
|------|------|
| `batch_ring_q.py` | 新增：CLI 入口、文件发现、逐文件编排、日志与总结 |
| `analysis/multimode.py` | 新增：`ModeFamily`/`ResonanceFit`/`MultiModeResult`、`detect_resonances`、`separate_modes`、`analyze_multimode` |
| `visualization/ring_report.py` | 新增：`plot_multimode_report`（单文件综合图） |
| `core/io.py` | 新增：`detect_header_rows`、`load_spectrum` 封装 |
| `tests/test_multimode.py` | 新增：多模式分离与 Q 提取单测 |
| `tests/test_io_header.py` | 新增：表头探测单测 |
| `requirements.txt` / 文档 | 备注 pytest 为开发依赖 |

不改动 `gui/`、`analysis/ring.py`、`analysis/peak.py`、`analysis/fitting.py`（仅复用）、`visualization/plotter.py`。
