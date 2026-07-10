"""
YotonBase - 简易关系型数据库核心（MySQL 版）
功能：
  1. 基础 CRUD（Create/Read/Update/Delete）
  2. 创意功能①：智能数据导出（CSV/JSON）
  3. 创意功能②：操作历史回溯（Undo/Redo）
"""

import json
import csv
import copy
import os
import pymysql
from typing import Any, Optional

# ============================================================
#  MySQL 连接配置
# ============================================================
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",
    "charset": "utf8mb4",
}


def get_connection():
    """获取数据库连接（自动连接 yotonbase 数据库）"""
    conn = pymysql.connect(**DB_CONFIG, database="yotonbase",
                           cursorclass=pymysql.cursors.DictCursor)
    return conn


def init_database():
    """初始化 yotonbase 数据库（如不存在则创建）"""
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS yotonbase "
                   "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.commit()
    cursor.close()
    conn.close()

    # 创建元数据表
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS __yotonbase_meta__ (
            table_name VARCHAR(128) PRIMARY KEY,
            columns_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    conn.commit()
    cursor.close()
    conn.close()


# ============================================================
#  历史记录栈（支持 Undo/Redo）
# ============================================================
class HistoryStack:
    """操作历史管理器，记录 SQL 语句用于撤销和重做
    每个操作存储为 (forward_sql, forward_params, backward_sql, backward_params, description, op_type)
    forward_sql/backward_sql 可以是普通 SQL 字符串，也可以是 JSON 字符串（复杂操作）
    """

    def __init__(self, max_size: int = 50):
        self._undo_stack = []   # 每个元素: (f_sql, f_params, b_sql, b_params, desc, tp)
        self._redo_stack = []
        self._max_size = max_size

    def push(self, forward_sql: str, backward_sql: str,
             description: str = "", op_type: str = "other",
             forward_params: tuple = None, backward_params: tuple = None) -> None:
        """保存一次操作"""
        if len(self._undo_stack) >= self._max_size:
            self._undo_stack.pop(0)
        self._undo_stack.append((forward_sql, forward_params, backward_sql, backward_params, description, op_type))
        self._redo_stack.clear()

    def undo(self) -> Optional[tuple]:
        """撤销：返回 (sql, params) 元组"""
        if not self._undo_stack:
            return None
        f_sql, f_params, b_sql, b_params, desc, tp = self._undo_stack.pop()
        self._redo_stack.append((f_sql, f_params, b_sql, b_params, desc, tp))
        return (b_sql, b_params)

    def redo(self) -> Optional[tuple]:
        """重做：返回 (sql, params) 元组"""
        if not self._redo_stack:
            return None
        f_sql, f_params, b_sql, b_params, desc, tp = self._redo_stack.pop()
        self._undo_stack.append((f_sql, f_params, b_sql, b_params, desc, tp))
        return (f_sql, f_params)

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def undo_count(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        return len(self._redo_stack)

    def get_undo_list(self) -> list[dict]:
        """获取可撤销的操作列表（带人类可读描述），索引 0 = 最近一步"""
        result = []
        for i in range(len(self._undo_stack) - 1, -1, -1):
            item = self._undo_stack[i]
            result.append({
                "index": len(self._undo_stack) - i,
                "description": item[4],
                "type": item[5],
            })
        return result

    def get_redo_list(self) -> list[dict]:
        """获取可重做的操作列表（带人类可读描述），索引 0 = 最近一步"""
        result = []
        for i in range(len(self._redo_stack) - 1, -1, -1):
            item = self._redo_stack[i]
            result.append({
                "index": len(self._redo_stack) - i,
                "description": item[4],
                "type": item[5],
            })
        return result


# ============================================================
#  YotonBase 数据库引擎（MySQL 版）
# ============================================================
class YotonBase:
    """
    YotonBase 数据库引擎（MySQL 版）
    管理多张 MySQL 表，提供 CRUD、导出、历史回溯功能
    """

    def __init__(self, db_name: str = "yotonbase"):
        self.db_name = db_name
        self.history = HistoryStack(max_size=50)
        init_database()

    def _conn(self):
        return get_connection()

    # -------------------- 表管理 --------------------
    def create_table(self, name: str, columns: list[str]) -> None:
        """创建表（在 MySQL 中创建物理表）"""
        if len(columns) < 1:
            raise ValueError("至少需要一列")
        conn = self._conn()
        cursor = conn.cursor()
        try:
            # 检查是否存在
            cursor.execute("SHOW TABLES LIKE %s", (name,))
            if cursor.fetchone():
                raise ValueError(f"表 '{name}' 已存在")

            # 第一列作为 VARCHAR 主键
            pk = columns[0]
            col_defs = [f"`{pk}` VARCHAR(255) NOT NULL PRIMARY KEY"]
            for col in columns[1:]:
                col_defs.append(f"`{col}` TEXT")

            ddl = f"CREATE TABLE `{name}` ({', '.join(col_defs)}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            cursor.execute(ddl)

            # 记录元数据
            cursor.execute(
                "INSERT INTO __yotonbase_meta__ (table_name, columns_json) VALUES (%s, %s)",
                (name, json.dumps(columns, ensure_ascii=False))
            )
            conn.commit()

            # 记录历史（反向操作为 DROP TABLE）
            self.history.push(
                forward_sql=f"DROP TABLE `{name}`",
                backward_sql=json.dumps({
                    "action": "restore_table",
                    "name": name,
                    "create_sql": ddl,
                    "rows": "[]",
                    "columns": json.dumps(columns, ensure_ascii=False)
                }, ensure_ascii=False),
                description=f"创建表「{name}」",
                op_type="create"
            )
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def drop_table(self, name: str) -> None:
        """删除表"""
        conn = self._conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SHOW TABLES LIKE %s", (name,))
            if not cursor.fetchone():
                raise ValueError(f"表 '{name}' 不存在")

            # 备份表结构和数据以便撤销
            cursor.execute("SELECT columns_json FROM __yotonbase_meta__ WHERE table_name = %s", (name,))
            meta = cursor.fetchone()
            columns = json.loads(meta["columns_json"]) if meta else ["id"]

            cursor.execute(f"SHOW CREATE TABLE `{name}`")
            create_sql = cursor.fetchone()["Create Table"]

            # 备份所有行数据（用于 undo 时恢复）
            cursor.execute(f"SELECT * FROM `{name}`")
            rows = cursor.fetchall()
            rows_json = json.dumps(rows, ensure_ascii=False, default=str)

            cursor.execute(f"DROP TABLE `{name}`")
            cursor.execute("DELETE FROM __yotonbase_meta__ WHERE table_name = %s", (name,))
            conn.commit()

            # 构造反向 SQL（完整重建语句）
            backward_sql = json.dumps({
                "action": "restore_table",
                "name": name,
                "create_sql": create_sql,
                "rows": rows_json,
                "columns": json.dumps(columns, ensure_ascii=False)
            }, ensure_ascii=False)

            self.history.push(
                forward_sql=f"DROP TABLE `{name}`",
                backward_sql=backward_sql,
                description=f"删除表「{name}」",
                op_type="drop"
            )
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def get_table(self, name: str) -> dict:
        """获取表信息"""
        conn = self._conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SHOW TABLES LIKE %s", (name,))
            if not cursor.fetchone():
                raise ValueError(f"表 '{name}' 不存在")
            cursor.execute("SELECT columns_json FROM __yotonbase_meta__ WHERE table_name = %s", (name,))
            row = cursor.fetchone()
            columns = json.loads(row["columns_json"]) if row else []
            cursor.execute(f"SELECT COUNT(*) AS cnt FROM `{name}`")
            count = cursor.fetchone()["cnt"]
            return {"name": name, "columns": columns, "row_count": count}
        finally:
            cursor.close()
            conn.close()

    def list_tables(self) -> list[str]:
        conn = self._conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT table_name FROM __yotonbase_meta__ ORDER BY created_at"
            )
            return [row["table_name"] for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()

    # -------------------- CRUD 操作 --------------------
    def insert(self, table_name: str, row: dict) -> dict:
        """插入一行"""
        conn = self._conn()
        cursor = conn.cursor()
        try:
            table = self.get_table(table_name)
            columns = table["columns"]
            pk = columns[0]

            # 主键不能为空
            if pk not in row or not row[pk]:
                raise ValueError(f"主键 '{pk}' 不能为空")

            # 构建 INSERT
            fields = []
            placeholders = []
            values = []
            for col in columns:
                if col in row:
                    fields.append(f"`{col}`")
                    placeholders.append("%s")
                    values.append(str(row[col]))
            sql = f"INSERT INTO `{table_name}` ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(sql, values)
            conn.commit()

            # 记录历史（反向操作为 DELETE）
            pk_val = str(row[pk])
            self.history.push(
                forward_sql=sql,
                forward_params=tuple(values),
                backward_sql=f"DELETE FROM `{table_name}` WHERE `{pk}` = %s",
                backward_params=(pk_val,),
                description=f"插入「{table_name}」→ {pk}={pk_val}",
                op_type="insert"
            )
            return dict(row)
        except pymysql.err.IntegrityError:
            conn.rollback()
            raise ValueError(f"主键 '{row.get(columns[0], '')}' 已存在")
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def query(self, table_name: str, conditions: Optional[dict] = None) -> list[dict]:
        """条件查询"""
        conn = self._conn()
        cursor = conn.cursor()
        try:
            if conditions:
                where_parts = []
                values = []
                for k, v in conditions.items():
                    where_parts.append(f"`{k}` = %s")
                    values.append(str(v))
                where_clause = " AND ".join(where_parts)
                sql = f"SELECT * FROM `{table_name}` WHERE {where_clause}"
                cursor.execute(sql, values)
            else:
                sql = f"SELECT * FROM `{table_name}`"
                cursor.execute(sql)
            rows = cursor.fetchall()
            # 转换所有值为字符串以便前端展示
            return [{k: str(v) if v is not None else "" for k, v in row.items()} for row in rows]
        finally:
            cursor.close()
            conn.close()

    def query_by_pk(self, table_name: str, pk_value: Any) -> Optional[dict]:
        table = self.get_table(table_name)
        pk = table["columns"][0]
        rows = self.query(table_name, {pk: pk_value})
        return rows[0] if rows else None

    def update(self, table_name: str, pk_value: Any, new_values: dict) -> Optional[dict]:
        """按主键更新"""
        conn = self._conn()
        cursor = conn.cursor()
        try:
            table = self.get_table(table_name)
            pk = table["columns"][0]

            # 先查旧值
            old = self.query_by_pk(table_name, pk_value)
            if not old:
                return None

            set_parts = []
            values = []
            for k, v in new_values.items():
                if k == pk:
                    continue  # 不允许改主键
                set_parts.append(f"`{k}` = %s")
                values.append(str(v))
            if not set_parts:
                return old

            values.append(str(pk_value))
            sql = f"UPDATE `{table_name}` SET {', '.join(set_parts)} WHERE `{pk}` = %s"
            cursor.execute(sql, values)
            conn.commit()

            # 反向操作：恢复旧值
            old_set = []
            old_vals = []
            for k, v in old.items():
                if k == pk:
                    continue
                old_set.append(f"`{k}` = %s")
                old_vals.append(str(v) if v is not None else "")
            old_vals.append(str(pk_value))
            backward_sql = f"UPDATE `{table_name}` SET {', '.join(old_set)} WHERE `{pk}` = %s"

            self.history.push(
                forward_sql=sql, forward_params=tuple(values),
                backward_sql=backward_sql, backward_params=tuple(old_vals),
                description=f"更新「{table_name}」→ {pk}={pk_value}",
                op_type="update"
            )

            return self.query_by_pk(table_name, pk_value)
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def delete(self, table_name: str, pk_value: Any) -> Optional[dict]:
        """按主键删除"""
        conn = self._conn()
        cursor = conn.cursor()
        try:
            table = self.get_table(table_name)
            pk = table["columns"][0]

            # 先查旧值
            old = self.query_by_pk(table_name, pk_value)
            if not old:
                return None

            sql = f"DELETE FROM `{table_name}` WHERE `{pk}` = %s"
            cursor.execute(sql, (str(pk_value),))
            conn.commit()

            # 反向操作：重新插入
            fields = ", ".join(f"`{k}`" for k in old.keys())
            placeholders = ", ".join(["%s"] * len(old))
            values = [str(v) if v is not None else "" for v in old.values()]
            backward_sql = f"INSERT INTO `{table_name}` ({fields}) VALUES ({placeholders})"

            self.history.push(
                forward_sql=sql, forward_params=(str(pk_value),),
                backward_sql=backward_sql, backward_params=tuple(values),
                description=f"删除「{table_name}」→ {pk}={pk_value}",
                op_type="delete"
            )

            return old
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    # -------------------- 创意功能①：智能数据导出 --------------------
    def export_csv(self, table_name: str, filepath: str) -> int:
        """将表数据导出为 CSV 文件"""
        rows = self.query(table_name)
        table = self.get_table(table_name)
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=table["columns"])
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)

    def export_json(self, table_name: str, filepath: str) -> int:
        """将表数据导出为 JSON 文件"""
        rows = self.query(table_name)
        table = self.get_table(table_name)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"name": table_name, "columns": table["columns"], "rows": rows},
                      f, ensure_ascii=False, indent=2)
        return len(rows)

    def export_query_csv(self, table_name: str, filepath: str,
                         conditions: Optional[dict] = None) -> int:
        """按条件查询后导出 CSV"""
        rows = self.query(table_name, conditions)
        if not rows:
            return 0
        table = self.get_table(table_name)
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=table["columns"])
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)

    def import_csv(self, table_name: str, filepath: str) -> int:
        """从 CSV 文件导入数据到表中"""
        table = self.get_table(table_name)
        columns = table["columns"]
        count = 0
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    self.insert(table_name, {c: row.get(c, "") for c in columns})
                    count += 1
                except ValueError:
                    pass  # 跳过重复主键
        return count

    # -------------------- 创意功能②：操作历史回溯 --------------------
    def undo(self) -> bool:
        """撤销上一步操作"""
        result = self.history.undo()
        if result is None:
            return False
        sql, params = result
        return self._execute_history_sql(sql, params)

    def redo(self) -> bool:
        """重做已撤销的操作"""
        result = self.history.redo()
        if result is None:
            return False
        sql, params = result
        return self._execute_history_sql(sql, params)

    def _execute_history_sql(self, sql: str, params: tuple = None) -> bool:
        """执行历史回溯的 SQL（支持参数化查询和 JSON 格式的复杂操作）"""
        conn = self._conn()
        cursor = conn.cursor()
        try:
            if sql.startswith("{"):
                # JSON 格式的复杂操作（如恢复删除的表）
                info = json.loads(sql)
                action = info.get("action")
                if action == "restore_table":
                    cursor.execute(info["create_sql"])
                    rows = json.loads(info["rows"])
                    if rows:
                        for row in rows:
                            keys = list(row.keys())
                            fields = ", ".join(f"`{k}`" for k in keys)
                            placeholders = ", ".join(["%s"] * len(keys))
                            values = [str(row[k]) if row[k] is not None else "" for k in keys]
                            cursor.execute(
                                f"INSERT INTO `{info['name']}` ({fields}) VALUES ({placeholders})",
                                values
                            )
                    cursor.execute(
                        "INSERT INTO __yotonbase_meta__ (table_name, columns_json) VALUES (%s, %s)",
                        (info["name"], info["columns"])
                    )
                else:
                    self._exec_sql(cursor, sql, params)
            else:
                self._exec_sql(cursor, sql, params)
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _exec_sql(cursor, sql: str, params: tuple = None) -> None:
        """执行 SQL，自动处理有无参数的情况"""
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

    @property
    def can_undo(self) -> bool:
        return self.history.can_undo

    @property
    def can_redo(self) -> bool:
        return self.history.can_redo

    def get_history_status(self) -> dict:
        """获取当前历史状态（含详细操作列表）"""
        return {
            "undo_count": self.history.undo_count,
            "redo_count": self.history.redo_count,
            "can_undo": self.history.can_undo,
            "can_redo": self.history.can_redo,
            "undo_list": self.history.get_undo_list(),
            "redo_list": self.history.get_redo_list(),
        }

    # -------------------- 持久化（保留接口兼容性，MySQL 自动持久化） --------------------
    def save_to_file(self, filepath: str) -> None:
        """MySQL 模式不需要此操作（数据自动持久化）"""
        pass

    @staticmethod
    def load_from_file(filepath: str) -> "YotonBase":
        """从文件路径创建实例（MySQL 模式仅用于初始化）"""
        return YotonBase("yotonbase")


# ============================================================
#  示例用法
# ============================================================
if __name__ == "__main__":
    db = YotonBase("学生管理系统")

    # 创建表
    db.create_table("students", ["学号", "姓名", "年龄", "专业"])

    # 插入数据
    db.insert("students", {"学号": "2024001", "姓名": "张三", "年龄": "20", "专业": "计算机科学"})
    db.insert("students", {"学号": "2024002", "姓名": "李四", "年龄": "21", "专业": "软件工程"})
    db.insert("students", {"学号": "2024003", "姓名": "王五", "年龄": "19", "专业": "数据科学"})

    print("所有学生:", db.query("students"))

    # 更新
    db.update("students", "2024001", {"年龄": "21"})
    print("更新后:", db.query_by_pk("students", "2024001"))

    # 导出 CSV
    db.export_csv("students", "students.csv")
    print("已导出 students.csv")

    # Undo 撤销更新
    db.undo()
    print("撤销后:", db.query_by_pk("students", "2024001"))

    # Redo 重做
    db.redo()
    print("重做后:", db.query_by_pk("students", "2024001"))
