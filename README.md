# YotonBase 数据库管理系统

一个基于 Python 的简易关系型数据库系统，包含完整的前后端实现，支持 CRUD、操作历史回溯（Undo/Redo）、多格式数据导出/导入。

---

## 项目结构

```
YotonBase/
├── database/
│   └── yotonbase.py          # YotonBase 数据库核心引擎（MySQL 版）
├── server/
│   ├── app.py                # Flask 后端 API 服务
│   ├── static/
│   │   └── index.html        # 前端管理界面
│   └── exports/              # 导出文件目录（自动创建）
├── requirements.txt          # Python 依赖
└── README.md                 # 本说明文档
```

## 环境要求

- **Python 3.9+**
- **MySQL 8.0**（需提前安装并启动，root 用户无密码或按需修改配置）

## 依赖库

| 依赖 | 版本 | 用途 |
|------|------|------|
| `flask` | >=2.3.0 | Web 后端框架 |
| `flask-cors` | >=4.0.0 | 跨域请求支持 |
| `pymysql` | >=1.1.0 | MySQL 数据库驱动 |

## 快速开始（3 步）

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 确保 MySQL 服务已启动（默认 root@127.0.0.1:3306，无密码）

# 3. 启动服务
python server/app.py
```

启动后浏览器访问：**http://127.0.0.1:5000/**

## MySQL 连接配置

如需修改数据库连接信息，编辑 `database/yotonbase.py` 顶部的 `DB_CONFIG`：

```python
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",          # 修改为你的 MySQL 密码
    "charset": "utf8mb4",
}
```

## 功能特性

### 基础功能（CRUD）
- **Create**：创建数据表、插入记录（第一列自动作为主键）
- **Read**：全表查询、条件查询、按主键查询
- **Update**：按主键更新记录
- **Delete**：按主键删除记录、删除整表

### 创意功能①：智能数据导出/导入
- 导出为 **CSV** 格式（可用 Excel 打开）
- 导出为 **JSON** 格式
- 从 CSV 文件导入数据
- 支持按条件筛选后导出

### 创意功能②：操作历史回溯（Undo/Redo）
- 每次增删改操作自动记录
- **撤销（Undo）**：回退到上一步操作前的状态
- **重做（Redo）**：恢复被撤销的操作
- 最多保存 50 步历史记录
- 操作历史详情弹窗，可查看每步描述

## 设计思路

### 技术架构

```
前端页面 (index.html)  ←→  HTTP API  ←→  Flask 后端 (app.py)  ←→  YotonBase 引擎 (yotonbase.py)  ←→  MySQL
```

### 核心设计

1. **前后端分离**：纯 HTML/CSS/JS 前端 + Flask RESTful API，接口清晰可独立调用
2. **参数化 SQL**：所有 SQL 使用 `%s` 占位符 + 参数元组执行，防止 SQL 注入
3. **历史栈机制**：`HistoryStack` 类维护 Undo/Redo 两个栈，每个操作存储 `(forward_sql, forward_params, backward_sql, backward_params, description, type)` 六元组，撤销/重做时直接取出对应 SQL+参数执行
4. **复杂操作 JSON 化**：创建表/删表的撤销涉及重建表+恢复数据，使用 JSON 格式封装完整操作描述
5. **元数据表**：`__yotonbase_meta__` 表存储所有用户表的列定义，实现 schema 管理
6. **主键设计**：第一列自动作为 VARCHAR 主键，简化操作但限制主键类型

### API 接口一览

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/tables` | 列出所有表 |
| POST | `/api/tables` | 创建表 |
| DELETE | `/api/tables/<name>` | 删除表 |
| GET | `/api/tables/<name>/schema` | 获取表结构 |
| GET | `/api/tables/<name>/rows` | 查询行（支持 `?key=value`） |
| POST | `/api/tables/<name>/rows` | 插入行 |
| PUT | `/api/tables/<name>/rows/<pk>` | 更新行 |
| DELETE | `/api/tables/<name>/rows/<pk>` | 删除行 |
| POST | `/api/tables/<name>/export/csv` | 导出 CSV |
| POST | `/api/tables/<name>/export/json` | 导出 JSON |
| GET | `/api/history` | 获取历史状态 |
| POST | `/api/history/undo` | 撤销 |
| POST | `/api/history/redo` | 重做 |

## 技术栈

- **后端**：Python + Flask
- **前端**：原生 HTML + CSS + JavaScript
- **数据存储**：MySQL 8.0（通过 pymysql 驱动）
- **数据库引擎**：YotonBase 自研引擎
