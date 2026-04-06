# SpectraLib Specification

核心数据处理库，负责 CSV 读取、数据管理和绘图。

## 模块概述

| 组件 | 职责 |
|------|------|
| `read_santec_csv()` | 解析单个 SANTEC CSV 文件 |
| `read_csv_arrays()` | 批量加载文件夹中的 CSV |
| `SpectraManager` | 数据容器，提供统一访问接口 |
| `plot_publication()` | 生成出版质量图像 |

---

## CSV 读取 (`read_santec_csv`)

### 输入
- `filepath`: CSV 文件路径
- `data_type`: `'auto'` | `'loss'` | `'raw'`
- `reference_path`: 可选，参考文件路径（用于 raw 模式）
- `skiprows`: 跳过行数，默认 14

### 输出
```python
{
    'wavelength': np.ndarray,  # 波长 (nm)
    'loss': np.ndarray,        # 插入损耗 (dB)
    'data_type': str,          # 实际检测到的类型
    'ranges': list[int],       # 量程编号列表
    'threshold': list,         # 多量程拼接阈值
    'meta': dict,              # 文件头元数据
}
```

### 行为规范

1. **格式检测优先级**
   - `data_type='auto'` 时：文件名 → 列标题 → 默认 loss

2. **多量程拼接** (raw 模式)
   - 从文件名解析 `_range123` 格式
   - 若解析失败，按中值降序自动分配量程
   - 使用 `RANGE_LIMITS` 阈值拼接重叠区

3. **参考文件减法**
   - 仅 raw 模式生效
   - 波长不匹配时自动插值

### 边界条件
- 文件不存在 → 抛出异常
- 无有效数据点 → 返回空数组
- 重复 x 值 → 取平均后排序

---

## 数据管理器 (`SpectraManager`)

### 构造方式
```python
# 从文件夹加载
mgr = SpectraManager.from_folder(folder, data_type='auto', reference_path=None)

# 从字典构建
mgr = SpectraManager.from_data(data_dict)
```

### 核心方法

#### `get_xy(key_or_index)`
返回 `(wavelength, loss)` numpy 数组。

| 参数 | 类型 | 说明 |
|------|------|------|
| `key_or_index` | int \| str | 索引号或完整键名 |
| 返回 | tuple[np.ndarray, np.ndarray] | (x, y) |

#### `_parse_var_key(key)` (静态)
解析键名，提取元数据。

**键名格式：**
```
{core}_step{step}_range{range}_source{source}dbm_type{dtype}_array
```

**返回字段：**
- `device`: 器件名称
- `device_no`: 器件编号
- `port`: 端口号
- `start_nm`, `end_nm`: 波长范围
- `step`: 步长
- `source_dbm`: 光源功率

---

## 绘图 (`plot_publication`)

### 输入
```python
data_list = [
    {'x': x1, 'y': y1, 'label': 'A', 'color': '#1f77b4'},
    {'x': x2, 'y': y2, 'label': 'B'},
]
fig, ax = plot_publication(data_list, xlabel='Wavelength (nm)', ylabel='IL (dB)')
```

### 输出规格
- 字体：Times New Roman, bold
- 刻度：向内，12pt
- 边框：2pt 粗细
- 图例：无框，右下角

---

## 工具函数

### `sanitize_xy(x, y)`
清理数据：去 NaN → 排序 → 重复 x 取平均

### `interp_on_grid(x_src, y_src, x_dst, mode='edge')`
插值到目标网格。
- `mode='edge'`: 边界延拓
- `mode='none'`: 边界填 NaN
- `mode='extrapolate'`: 线性外推

### `create_uniform_grid(start, end, step, decimals=None)`
生成均匀网格，自动吸附小数位。
