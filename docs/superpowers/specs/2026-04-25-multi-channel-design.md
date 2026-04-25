# 多通道数据支持设计

## 需求

SANTEC 光谱仪 CSV 文件可能包含多个通道的数据（如 CH1、CH2），当前系统只读取第一个通道。需要支持多通道独立加载、处理和展示。

## 数据格式

### Loss 多通道
```
Wavelength(nm),IL_M1_CH1,IL_M1_CH2
1500.000,-10.95,-35.76
```

### Raw 多通道
```
Wavelength(nm),Monitor-R1(dBm),Raw_M1-Ch1-R1(dBm),Raw_M1-Ch2-R1(dBm)
1500.000,7.55,-21.40,-22.10
```

## 方案：IO 层分通道

`read_santec_csv` 返回 `list[dict]`，每个元素是完整的单通道结果字典，新增 `'channel'` 字段。

### 列头通道检测规则

- **Loss**: 匹配 `IL` 关键词的列，按列头中的 `CH` + 数字区分通道
- **Raw**: 匹配 `Raw` 关键词的列，按列头中的 `Ch` + 数字区分通道
- 单通道文件返回 `[result_dict]`（一个元素的列表），向后兼容

### 数据流

```
read_santec_csv(filepath)
    → 检测通道数
    → 每个通道独立处理（loss 直接读列 / raw 拼接+减参考）
    → 返回 list[dict]，每个 dict 含 'channel' 字段

read_csv_arrays(folder)
    → 遍历文件，每个文件可能返回多个 result
    → 为每个通道生成独立的 key（含 channel 信息）

SpectraManager
    → 每个通道 = 一行数据
    → _parse_var_key 增加 channel 解析

GUI 表格
    → 新增 'channel' 列
    → 每个通道单独一行
```

### 修改文件

#### `core/io.py`

**`_detect_columns`** 改为返回通道映射：
```python
def _detect_columns(path, skip):
    # 返回 (data_type, channels)
    # channels: [{'col_idx': int, 'name': 'CH1'}, ...]
    # Loss: 匹配 IL_.*_CH(\d+)
    # Raw: 匹配 Raw.*[Cc]h(\d+)
```

**`read_santec_csv`** 改为返回 `list[dict]`：
```python
# 单通道: return [result_dict]
# 多通道: return [result_dict_ch1, result_dict_ch2]
# 每个 result_dict 结构不变，新增 'channel': 'CH1' 字段
```

**`read_csv_arrays`** 适配列表返回：
```python
results = read_santec_csv(filepath, ...)
for result in results:  # 遍历每个通道
    channel = result.get('channel', '')
    key = _build_key(...) + f'_ch{channel}'
    data_dict[key] = np.column_stack([result['wavelength'], result['loss']])
```

#### `core/manager.py`

**`_parse_var_key`** 增加通道解析：
```python
# 从 key 中提取 channel 信息
# 返回的 metadata 增加 'channel' 字段
```

**DataFrame** 增加 `channel` 列。

#### `gui/main_window.py`

**表格列** 增加 `channel`：
```python
cols = ['#', 'device', 'device_no', 'port', 'channel', 'start_nm', 'end_nm', 'step', 'range', 'source_dbm', 'data_type']
```

**`_populate_table`** 从 DataFrame 读取 channel 列显示。

### 向后兼容

- 单通道文件行为完全不变（返回 `[result_dict]`）
- 现有调用 `read_santec_csv` 的地方改为遍历列表
- `get_xy` 无需修改（每个通道已有独立 key）

## 测试

1. 多通道 Loss 文件：两个通道独立显示在表格中
2. 多通道 Raw 文件：每个通道独立拼接和减参考
3. 单通道文件：行为与改动前一致
4. 公式计算：可选择不同通道数据组合
