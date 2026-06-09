# FIFA 19 存档格式修复总结

## 状态：✅ 已修复

共发现并修复了 **3 个格式问题**，GUI 修改存档后游戏正常加载。

---

## 修复 1: 表尾部数据（Trailing Data）— `table.py`

RDBM 保存时每个表尾部只用 **4 字节**（仅 CRC-32/MPEG-2），而非原版的变长尾部（4/20/28/36 字节）。

```python
# table.py save() 方法中
new_trailing = struct.pack("<I", records_crc)  # 仅 4 字节 CRC
table_data += new_trailing
```

## 修复 2: FBCHUNKS SaveType 后的 5 字节 — `sav_file.py`

`"SaveType_Squads\0"` 之后有 5 字节（偏移 118-122）包含游戏专用哈希值，需归零：

```python
fbchunks = bytearray(self.fbchunks_header)
for i in range(118, 123):
    fbchunks[i] = 0  # 归零
```

## 修复 3: FBCHUNKS DataSize 字段 — `sav_file.py`

FBCHUNKS 头部的 `DataSize` 字段（字节 14-17, little-endian uint32）需遵循公式：

> **DataSize = 文件总大小 - 102**

其中 102 = 18（chunk 头部前缀）+ 84（chunk 尾部数据）。表大小变化后必须更新此值，否则游戏读数据超 EOF 导致加载失败。

```python
total_size = len(fbchunks) + len(db_data)
new_data_size = total_size - 102
fbchunks[14:18] = struct.pack("<I", new_data_size)
```

---

## 格式关键字段

### `field_count_raw`（表头字节 24-27）

| 格式 | `field_count_raw` 值 | CRC 算法 |
|------|---------------------|----------|
| 游戏原生格式 | `n_fields + 0x100`（如 118 → 374） | 游戏专用算法（非标准 CRC-32） |
| RDBM/编辑器格式 | `n_fields`（如 118） | **标准 CRC-32/MPEG-2** |

`field_count_raw` 相当于格式版本号。游戏根据它的值选择不同的 CRC 验证算法：

- **原版值**（`n_fields + 0x100`）→ 游戏使用自己的专有 CRC 算法验证记录数据
- **编辑器值**（`n_fields`）→ 游戏使用标准 CRC-32/MPEG-2（多项式 `0x04C11DB7`，init=`0xFFFFFFFF`，无 final XOR）

### 其他关键差异

1. **记录编码**：RDBM 从零重新编码所有记录（清零字段外的填充位），而游戏原生格式可能保留非零填充位
2. **表尾数据（Trailing Data）**：RDBM 统一使用 **24 字节**尾数据格式，而游戏原生格式的尾数据长度不一（4/20/28/36 字节）
3. **表头 CRC**：使用标准 CRC-32/MPEG-2，覆盖表头前 32 字节
4. **记录 CRC**：使用标准 CRC-32/MPEG-2，覆盖 `字段描述符 + 记录数据 + 压缩字符串数据`

## 修复方案

### 1. 写入 `field_count_raw = n_fields`

```python
# table.py save() 方法中
writer.write_raw_bytes(struct.pack("<I", self.n_fields))  # 不是 self._field_count_raw
```

### 2. 从零编码所有记录（不保留原始填充位）

```python
# table.py save() 方法中
for rec_idx in range(self.n_valid_records):
    record = self.records[rec_idx]
    rec_bytes = self._write_record(record, sorted_fields)
    # 零填充到 record_size
    if len(rec_bytes) < self.record_size:
        rec_bytes += b"\x00" * (self.record_size - len(rec_bytes))
    writer.write_raw_bytes(rec_bytes)
```

### 3. 使用 24 字节统一尾数据格式

```python
TRAILING_SIZE = 24
records_crc = _compute_crc(content)  # CRC-32/MPEG-2
# 保留原始元数据（如有），不足补零
meta = self._trailing_data[4:TRAILING_SIZE]
meta += b"\x00" * (TRAILING_SIZE - 4 - len(meta))
new_trailing = struct.pack("<I", records_crc) + meta[:TRAILING_SIZE - 4]
```

### 4. 重新计算所有 CRC

- **表头 CRC**：`_compute_crc(table_data[:32])`
- **记录 CRC**：`_compute_crc(FD + records + CS)`
- **短名 CRC**：`_compute_crc(directory_bytes)`
- **DB 头 CRC**：`_compute_crc(header[:20])`

### 5. 重建 DB 目录偏移量

由于所有表的尾数据统一为 24 字节（和游戏原生长度不同），`DbFile.save()` 需要重新计算并写入所有表的偏移量，并更新 DB 文件长度。

## CRC-32/MPEG-2 算法

```python
POLY = 0x04C11DB7  # 非反射多项式

def _compute_crc(data: bytes) -> int:
    """CRC-32/MPEG-2: init=0xFFFFFFFF, no final XOR"""
    table = [...]  # 256 项预计算查找表
    crc = 0xFFFFFFFF
    for byte in data:
        crc = ((crc << 8) ^ table[((crc >> 24) ^ byte) & 0xFF]) & 0xFFFFFFFF
    return crc
```

验证向量：`_compute_crc(b"123456789")` = `0x0376E6E7`

## 验证方法

通过对比 RDBM 19 的输出文件确认格式正确性：

1. 用 RDBM 修改同一文件的一个字段（如 composure 50→99）
2. 保存后，对比 RDBM 输出与原始文件的差异
3. 分析差异，提取格式规则
4. 在我们的保存管线中实现相同规则
5. 用 RDBM 输出作为基底，只修改目标数据+CRC，确认游戏接受

## 关键文件

| 文件 | 作用 |
|------|------|
| `fifa19-editor/core/table.py` | 表序列化：`save()`、`_write_record()`、`_compute_crc()` |
| `fifa19-editor/core/db_file.py` | DB 容器：目录重建、头 CRC、短名 CRC |
| `fifa19-editor/core/db_writer.py` | 位压缩写入器 |
| `fifa19-editor/core/db_reader.py` | 位压缩读取器 |

## 参考工具

- **RDBM 19**（Revolution Database Master 19）：已验证可正确保存 FIFA 19 存档
- **FifaLibrary19.dll**：RDBM 的核心库，使用 `ComputeCrcDb11`（= CRC-32/MPEG-2）
- **FifaLibrary14**（C# 开源）：FIFA 14 的参考实现，CRC 算法和较新版本一致
