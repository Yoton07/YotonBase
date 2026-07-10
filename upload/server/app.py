"""
YotonBase 后端 API 服务（MySQL 版）
使用 Flask 提供 RESTful 接口，供前端调用
"""

import sys
import os

# 将 database 目录加入路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from yotonbase import YotonBase

app = Flask(__name__)
CORS(app)

# 全局数据库实例（MySQL 模式）
db = YotonBase("yotonbase")


# ==================== 表管理 ====================
@app.route("/api/tables", methods=["GET"])
def list_tables():
    return jsonify({"tables": db.list_tables()})


@app.route("/api/tables", methods=["POST"])
def create_table():
    data = request.json
    try:
        db.create_table(data["name"], data["columns"])
        return jsonify({"ok": True, "message": f"表 '{data['name']}' 创建成功"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/tables/<name>", methods=["DELETE"])
def drop_table(name):
    try:
        db.drop_table(name)
        return jsonify({"ok": True, "message": f"表 '{name}' 已删除"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/tables/<name>/schema", methods=["GET"])
def table_schema(name):
    try:
        t = db.get_table(name)
        return jsonify({"columns": t["columns"], "row_count": t["row_count"]})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ==================== CRUD ====================
@app.route("/api/tables/<name>/rows", methods=["GET"])
def query_rows(name):
    """查询行，支持 ?key=value 条件筛选"""
    try:
        conditions = {}
        for key, value in request.args.items():
            conditions[key] = value
        rows = db.query(name, conditions if conditions else None)
        return jsonify({"rows": rows, "count": len(rows)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/tables/<name>/rows", methods=["POST"])
def insert_row(name):
    """插入一行"""
    try:
        row = request.json
        result = db.insert(name, row)
        return jsonify({"ok": True, "row": result})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/tables/<name>/rows/<pk_value>", methods=["PUT"])
def update_row(name, pk_value):
    """更新一行"""
    try:
        new_values = request.json
        result = db.update(name, pk_value, new_values)
        if result:
            return jsonify({"ok": True, "row": result})
        return jsonify({"ok": False, "error": "未找到该记录"}), 404
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/tables/<name>/rows/<pk_value>", methods=["DELETE"])
def delete_row(name, pk_value):
    """删除一行"""
    try:
        result = db.delete(name, pk_value)
        if result:
            return jsonify({"ok": True, "deleted": result})
        return jsonify({"ok": False, "error": "未找到该记录"}), 404
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


# ==================== 创意功能①：导出/导入 ====================
@app.route("/api/tables/<name>/export/csv", methods=["POST"])
def export_csv(name):
    """导出表为 CSV"""
    try:
        filepath = os.path.join(os.path.dirname(__file__), f"exports/{name}.csv")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        count = db.export_csv(name, filepath)
        return jsonify({"ok": True, "count": count, "filepath": filepath})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/tables/<name>/export/json", methods=["POST"])
def export_json(name):
    """导出表为 JSON"""
    try:
        filepath = os.path.join(os.path.dirname(__file__), f"exports/{name}.json")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        count = db.export_json(name, filepath)
        return jsonify({"ok": True, "count": count, "filepath": filepath})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


# ==================== 创意功能②：历史回溯 ====================
@app.route("/api/history", methods=["GET"])
def history_status():
    """获取历史状态"""
    return jsonify(db.get_history_status())


@app.route("/api/history/undo", methods=["POST"])
def undo():
    """撤销"""
    ok = db.undo()
    return jsonify({"ok": ok, "status": db.get_history_status()})


@app.route("/api/history/redo", methods=["POST"])
def redo():
    """重做"""
    ok = db.redo()
    return jsonify({"ok": ok, "status": db.get_history_status()})


# ==================== 静态文件 ====================
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ==================== 启动 ====================
if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "exports"), exist_ok=True)
    print("=" * 55)
    print("  YotonBase 数据库服务已启动 (MySQL 版)")
    print("  访问地址: http://127.0.0.1:5000/")
    print("=" * 55)
    print("  提示：请确保 MySQL 服务已启动")
    print("  默认连接: root@127.0.0.1:3306（无密码）")
    print("  如需修改，编辑 database/yotonbase.py 中的 DB_CONFIG")
    print("  如需关闭服务，请按 Ctrl+C")
    print("=" * 55)
    app.run(host="127.0.0.1", port=5000, debug=False)
