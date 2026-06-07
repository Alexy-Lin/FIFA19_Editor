# FIFA 19 存档编辑器 — 技术调研总结

> 创建日期: 2026-06-07
> 目标: 编辑 FIFA 19 阵容存档文件（Squads*.sav），修改球员属性

---

## 一、文件格式解析

### 1.1 阵容文件 (.sav) 结构

工作区已有文件: `Squads20260423210221`（6,090,418 字节）

```
Offset 0:     "FBCHUNKS"     ← Frostbite Chunks 容器头 (146 字节)
Offset 146:   "DB\x00\x08"   ← 嵌入式数据库主体 (6,090,272 字节)
```

- **FBCHUNKS** 是 Frostbite 引擎的容器格式，146 字节的头部
- 后面紧跟着 `DB\x00\x08` 格式的自定义数据库
- 数据库使用**位压缩（bit-packed）** 二进制格式

### 1.2 DB 二进制格式（完全解密）

来源: Rinaldo 的开源库 **FifaLibrary14**（C#，位于 `github.com/ebeninca/CreationMaster17/FifaLibrary14/`）

#### 文件头 (24+ 字节)

| 偏移 | 大小 | 内容 |
|------|------|------|
| 0-1 | 2 | 魔数 "DB" |
| 2 | 1 | 0x00 |
| 3 | 1 | 0x08（版本号） |
| 4 | 1 | 平台 (0=PC, 1=Xbox) |
| 5-7 | 3 | 填充 0x00 |
| 8-11 | 4 | 文件总长度 (uint32 LE) |
| 12-15 | 4 | 保留 |
| 16-19 | 4 | 表数量 (uint32 LE) |
| 20-23 | 4 | CRC32 头部校验 |

#### 表目录

每张表:
| 大小 | 内容 |
|------|------|
| 4 字节 | 表短名（如 `players`） |
| 4 字节 | 表数据偏移 (uint32 LE) |

表目录后还有 4 字节 CRC32 ShortNames 校验。

#### 表结构

每张表包含:
- **字段描述符（FieldDescriptors）**: 
  - 字段类型 (0=字符串, 3=整数, 4=浮点, 13=短压缩字符串, 14=长压缩字符串)
  - 位偏移 (BitOffset)
  - 字段短名 (4 字节编码)
  - 位深度 (Depth)
- **CRC32 表头校验**
- **记录数 + 有效记录数**
- **记录数据**: 每条记录的字段按位压缩存储

#### 位压缩整数（核心算法）

**读取**（DbReader.PopIntegerPc）:
- 维护当前字节和当前位位置
- 逐位消费，跨字节边界读取
- 读完后加上 `RangeLow` 偏移值

**写入**（DbWriter.PushIntegerPc）:
- 值减去 `RangeLow`
- 按位逐位写入，跨字节边界
- 积累满一个字节后写出

**字符串**: null 终止，部分用 Huffman 压缩
**浮点数**: 标准 4 字节 IEEE 754

---

## 二、已获取的资源

### 2.1 工作区现有文件

| 文件 | 大小 | 来源 |
|------|------|------|
| `Squads20260423210221` | 6.0 MB | 用户 FIFA 19 阵容存档 |
| `fifa_ng_db-meta.xml` | 534 KB | 从 npm 包下载 |

### 2.2 关键开源参考

1. **FifaLibrary14**（Rinaldo, C#）⭐ 核心参考
   - 仓库: `github.com/ebeninca/CreationMaster17/FifaLibrary14/`
   - 关键文件:
     - `DbReader.cs` — 位压缩字段读取
     - `DbWriter.cs` — 位压缩字段写入
     - `DbFile.cs` — 文件容器（签名/表目录/CRC）
     - `FieldDescriptor.cs` — 字段元数据（类型枚举、位偏移、深度）
     - `Table.cs` — 表记录管理
     - `HuffmannTree.cs` — Huffman 压缩
   - 许可证: 开源（CreationMaster17 项目内）

2. **fifa-career-save-parser**（Sammy Griffiths, JavaScript）
   - 仓库: `github.com/sammygriffiths/fifa-career-save-parser`
   - 可读 FIFA 17~21 的 .sav 文件
   - 使用 `xml/19/fifa_ng_db-meta.xml` 映射字段名
   - **局限**: 只读，不支持写入

### 2.3 需要但未获取的文件

`fifa_ng_db.db` — 主数据库文件，位于 CPY 版的 `.cas` 打包文件中（`Data/Win32/superbundlelayout/`），需要 Frosty Editor 提取，或从 FIFA modding 社区下载。**可能不是必须的**，因为 .sav 已经包含了字段描述信息。

---

## 三、RDBM 工作流程

RDBM（Revolution DB Master）的操作方式:

1. **加载主数据库**: `File -> Open` → 选择 `fifa_ng_db.db` + `fifa_ng_db-meta.xml`
2. **加载存档**: 再打开 `Squads*.sav` 或 `Career*.sav`
3. **编辑**: 选中表（如 `players`），修改数据
4. **保存**: 写回存档文件

主数据库的作用是提供**完整的表结构参考**。但 `.sav` 文件内嵌的数据库已经包含字段描述符，理论上配合 `meta.xml` 即可工作。

---

## 四、推荐实现方案

### 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 语言 | **Python 3.10+** | 用户首选 |
| GUI | **PySide6** | Qt 表格编辑功能强大 |
| 数据库读写 | **自建核心库** | 移植 C# FifaLibrary14 (~1000 行) |

### 架构

```
fifa19-editor/
├── main.py                     # 入口
├── requirements.txt            # PySide6
├── fifa_ng_db-meta.xml         # 已下载，直接使用
│
├── core/                       # 核心库（移植自 FifaLibrary14）
│   ├── types.py               # 类型定义
│   ├── db_file.py             # 文件容器
│   ├── db_reader.py           # 位压缩读取
│   ├── db_writer.py           # 位压缩写入
│   ├── field_descriptor.py    # 字段元数据
│   ├── table.py               # 表记录管理
│   ├── record.py              # 单条记录
│   ├── huffman.py             # Huffman 压缩
│   ├── meta_parser.py         # 解析 fifa_ng_db-meta.xml
│   └── sav_file.py            # .sav 容器处理
│
├── ui/                        # GUI
│   ├── main_window.py         # 主窗口
│   ├── table_view.py          # 可编辑表格
│   ├── table_tree.py          # 表列表
│   └── search_bar.py          # 搜索
│
└── tests/                     # 测试
    ├── test_reader.py
    ├── test_writer.py
    └── test_roundtrip.py
```

### 实现步骤

#### Step 1: 核心库移植（按依赖顺序）

```
types.py → field_descriptor.py → db_reader.py → db_writer.py
  → record.py → table.py → db_file.py → meta_parser.py → sav_file.py
```

每层写单元测试验证。

#### Step 2: 字段类型枚举

```python
from enum import IntEnum

class EFieldTypes(IntEnum):
    String = 0
    Integer = 3
    Float = 4
    ShortCompressedString = 13
    LongCompressedString = 14
```

#### Step 3: 位压缩读写（核心算法）

```python
# 读取 (DbReader)
class DbReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.current_byte = 0
        self.current_bit_pos = 8  # 刚读完，需要加载下一个字节
    
    def read_bits(self, depth: int) -> int:
        """读取指定位深度的整数（位压缩）"""
        value = 0
        remaining = depth
        while remaining > 0:
            if self.current_bit_pos >= 8:
                self.current_byte = self.data[self.pos]
                self.pos += 1
                self.current_bit_pos = 0
            bits_in_byte = min(8 - self.current_bit_pos, remaining)
            shift = 8 - self.current_bit_pos - bits_in_byte
            mask = (1 << bits_in_byte) - 1
            bits = (self.current_byte >> shift) & mask
            value = (value << bits_in_byte) | bits
            self.current_bit_pos += bits_in_byte
            remaining -= bits_in_byte
        return value
    
    def pop_integer(self, field: FieldDescriptor) -> int:
        raw = self.read_bits(field.depth)
        return raw + field.range_low
    
    def read_string(self, length: int) -> str:
        """读取 null 终止字符串"""
        chars = []
        while len(chars) < length:
            b = self.data[self.pos]
            self.pos += 1
            if b == 0:
                # 跳过剩余填充
                self.pos += length - len(chars) - 1
                break
            chars.append(chr(b))
        return ''.join(chars)
    
    def read_float(self) -> float:
        """读取 4 字节浮点数"""
        import struct
        val = struct.unpack('<f', self.data[self.pos:self.pos+4])[0]
        self.pos += 4
        return val


# 写入 (DbWriter)
class DbWriter:
    def __init__(self):
        self.buffer = bytearray()
        self.current_byte = 0
        self.current_bit_pos = 0
    
    def write_bits(self, value: int, depth: int):
        """写入指定位深度的整数（位压缩）"""
        remaining = depth
        while remaining > 0:
            bits_in_byte = min(8 - self.current_bit_pos, remaining)
            shift = remaining - bits_in_byte
            byte_val = (value >> shift) & ((1 << bits_in_byte) - 1)
            self.current_byte = (self.current_byte << bits_in_byte) | byte_val
            self.current_bit_pos += bits_in_byte
            remaining -= bits_in_byte
            if self.current_bit_pos >= 8:
                self.buffer.append(self.current_byte & 0xFF)
                self.current_byte = 0
                self.current_bit_pos = 0
    
    def push_integer(self, value: int, field: FieldDescriptor):
        raw = value - field.range_low
        self.write_bits(raw, field.depth)
    
    def flush(self):
        if self.current_bit_pos > 0:
            self.current_byte <<= (8 - self.current_bit_pos)
            self.buffer.append(self.current_byte & 0xFF)
```

#### Step 4: 文件容器 (DbFile)

```python
class DbFile:
    SIGNATURE = b'DB\x00\x08'
    
    def load(self, data: bytes):
        # 验证签名
        assert data[:4] == self.SIGNATURE
        # 解析头部
        self.platform = data[4]           # 0=PC
        self.file_length = struct.unpack('<I', data[8:12])[0]
        self.n_tables = struct.unpack('<I', data[16:20])[0]
        # 读取表目录
        pos = 24
        tables = []
        for _ in range(self.n_tables):
            name = data[pos:pos+4].rstrip(b'\x00').decode()
            offset = struct.unpack('<I', data[pos+4:pos+8])[0]
            tables.append((name, offset))
            pos += 8
        # 读取每张表
        for name, offset in tables:
            table = Table()
            table.load(data, offset)
            self.tables[name] = table
    
    def save(self) -> bytes:
        # 重新组装二进制数据
        writer = DbWriter()
        # ... 写头部、表目录、表数据、CRC32
        return bytes(writer.buffer)
```

#### Step 5: .sav 容器处理

```python
class SavFile:
    DB_SIGNATURE = b'DB\x00\x08'
    
    def load(self, filepath: str):
        with open(filepath, 'rb') as f:
            data = f.read()
        # 扫描 DB 签名
        pos = data.find(self.DB_SIGNATURE)
        if pos == -1:
            raise ValueError("Not a valid FIFA save file")
        # 提取 FBCHUNKS 头
        self.fbchunks_header = data[:pos]
        # 加载 DB 数据库
        self.db = DbFile()
        self.db.load(data[pos:])
    
    def save(self, filepath: str):
        db_data = self.db.save()
        with open(filepath, 'wb') as f:
            f.write(self.fbchunks_header)
            f.write(db_data)
```

---

## 五、数据库表参考（核心表）

从 `fifa_ng_db-meta.xml` 中提取的关键表:

### `players` 表（球员主表）

| 字段名 | 短名 | 类型 | 深度 | 范围 | 说明 |
|--------|------|------|------|------|------|
| playerid | `ykFq` | INTEGER | 19 | 0-300000 | 球员 ID（主键） |
| firstname | (STRING) | STRING | 480 | - | 名 |
| lastname | (STRING) | STRING | 480 | - | 姓 |
| commonname | (STRING) | STRING | 480 | - | 常用名 |
| overallrating | INTEGER | 7 | 0-99 | 总评 |
| potential | INTEGER | 7 | 0-99 | 潜力 |
| preferredposition | `vjla` | INTEGER | 6 | 0-27 | 首选位置 |
| age | birthdate | INTEGER | - | - | 年龄（通过生日计算） |
| composure | INTEGER | 7 | 0-99 | 镇定（隐藏属性） |
| skillmoves | INTEGER | 3 | 0-4 | 花式星级 |
| weakfootabilitytype | INTEGER | 3 | 1-5 | 逆足 |
| attackingworkrate | INTEGER | 2 | 0-2 | 进攻积极性 |
| defensiveworkrate | INTEGER | 2 | 0-2 | 防守积极性 |
| bodytypecode | INTEGER | - | - | 体型代码 |

**常用位置编码**: 0=GK, 1=SW, 2=RWB, 3=RB, 4=CB, 5=LB, 6=LWB, 7=CDM, 8=RM, 9=CM, 10=LM, 11=CAM, 12=RF, 13=CF, 14=LF, 15=RW, 16=ST, 17=LW

### `teams` 表（球队表）
| 字段名 | 短名 | 深度 | 范围 |
|--------|------|------|------|
| teamid | `mCXg` | 18 | 1-200000 |
| teamname | STRING | 480 | - |
| overallrating | `UERs` | 7 | 0-99 |

### `teamplayerlinks` 表（球员球队关联）
| 字段名 | 短名 | 深度 | 范围 |
|--------|------|------|------|
| playerid | `ykFq` | 19 | 0-300000 |
| teamid | `mCXg` | 18 | 1-200000 |

---

## 六、常见问题

### Q: CPY 版主数据库在哪？
A: 打包在 `Data/Win32/superbundlelayout/*.cas` 文件中，需要用 Frosty Editor 的 Legacy Explorer 导出 `data/db/fifa_ng_db.db`。

### Q: 没有 fifa_ng_db.db 能工作吗？
A: 可能可以。`.sav` 文件内嵌的数据库已经包含字段描述符，配合 `fifa_ng_db-meta.xml` 应该能正常读取和修改。如果写入后游戏不认，再补充 `.db` 文件的支持。

### Q: 修改后游戏不认怎么办？
A: 可能原因及解决方案:
1. CRC32 校验没算对 — 移植时仔细检查 `ComputeAllCrc` 逻辑
2. FBCHUNKS 头损坏 — 保存时保留原始头
3. 字段深度/偏移不对 — 确保从 .sav 读取的 field descriptor 完整保留后回写
4. 需要清除缓存或重开档

### Q: 安全性如何？
A: 建议修改前复制一份原始存档到别处。编辑器只修改内存中的数据，保存时写入新文件（不覆盖原文件时可恢复）。

---

## 七、测试验证

1. 从 `Documents\FIFA 19\settings\` 复制 `Squads*.sav` 到工作区
2. 加载 `fifa_ng_db-meta.xml` + `.sav` 文件
3. 验证: 左侧显示 players, teams 等表名
4. 搜索 "Messi" → 定位到球员
5. 修改 `overallrating` (93 → 99) → 单元格变黄
6. 保存 → 放入游戏 `settings/` 目录 → 加载阵容 → 确认生效

---

## 八、参考链接

- FifaLibrary14 (C#, 核心参考): https://github.com/ebeninca/CreationMaster17/tree/master/FifaLibrary14
- fifa-career-save-parser (JS, 只读参考): https://github.com/sammygriffiths/fifa-career-save-parser
- FIFA 19 meta.xml (已下载): 工作区 `fifa_ng_db-meta.xml`
- Ultimate EA DB Master: https://dl.fifa-infinity.com/fc-26/ultimate-ea-db-master/
- Creation Wizard 19: https://www.balkanpesbox.com/forum/topic/3428-creation-wizard-2019/
