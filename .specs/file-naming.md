# File Naming Convention

SANTEC CSV 文件命名规范与解析规则。

## 标准命名格式

```
{chip}_{device}_{device_no}_{port}_{start}_{end}_step{step}_range{range}_source{power}dbm_{type}.csv
```

### 示例
```
chip1_wg_01_1_1500_1600_step1pm_range2_source0dbm_loss.csv
chip1_wg_01_2_1500_1600_step1pm_raw.csv
```

---

## 字段说明

| 字段 | 格式 | 示例 | 说明 |
|------|------|------|------|
| chip | 字符串 | `chip1` | 芯片标识 |
| device | 字符串 | `wg`, `ring` | 器件类型 |
| device_no | 数字 | `01`, `1` | 器件编号 |
| port | 数字 | `1`, `2` | 端口号 |
| start | 数字 (nm) | `1500` | 起始波长 |
| end | 数字 (nm) | `1600` | 终止波长 |
| step | 数字+单位 | `1pm`, `10pm` | 扫描步长 |
| range | 数字串 | `2`, `12`, `123` | 量程组合 |
| source | 数字 | `0`, `-10` | 光源功率 (dBm) |
| type | 固定值 | `loss`, `raw` | 数据类型 |

---

## 解析逻辑 (`_parse_var_key`)

### 键名生成
```python
key = f"{core}_step{step}_range{range}_source{source}_type{dtype}_array"
```

### core 解析

1. 移除 `step`, `range`, `source`, `type` 后缀
2. 按下划线分割
3. 识别 ≥100 的数字作为波长范围
4. 剩余部分按位置分配：
   - 4+ tokens: `chip_device_no_port`
   - 3 tokens: `device_no_port`
   - 2 tokens: `device_port`
   - 1 token: `device`

---

## 量程编码

| Range | 动态范围 | 典型用途 |
|-------|----------|----------|
| 1 | -30 ~ +10 dBm | 高功率 |
| 2 | -40 ~ 0 dBm | 常规 |
| 3 | -50 ~ -10 dBm | 中等损耗 |
| 4 | -60 ~ -20 dBm | 高损耗 |
| 5 | -80 ~ -30 dBm | 极高损耗 |

### 多量程文件
- `_range12`: 同时包含量程 1 和 2 的扫描
- `_range123`: 三量程拼接

---

## 数据类型

| 类型 | 列结构 | 处理方式 |
|------|--------|----------|
| `loss` | Wavelength, IL | 直接使用 |
| `raw` | Wavelength, Monitor, Raw1, Raw2... | 多量程拼接 + 参考减法 |

---

## 简短格式

如果文件名不符合标准格式，回退到文件头读取：

```
chip_device_port.csv
```

元数据从 CSV 前 14 行解析：
- Start Wavelength
- Stop Wavelength
- Step
- Source Power
