"""诊断检索问题"""
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.storage.note_store import NoteStore

store = NoteStore()

# 检查所有学生的笔记和分块
print("=== 数据库诊断 ===\n")

# 获取所有笔记
import sqlite3
conn = sqlite3.connect(store._db_path)
conn.row_factory = sqlite3.Row

students = conn.execute("SELECT DISTINCT student_id FROM notes").fetchall()
print(f"学生数量: {len(students)}")

for row in students:
    student_id = row["student_id"]
    notes = conn.execute("SELECT COUNT(*) as cnt FROM notes WHERE student_id = ?", (student_id,)).fetchone()
    chunks = conn.execute("""
        SELECT COUNT(*) as cnt FROM note_chunks c
        JOIN notes n ON c.note_id = n.id
        WHERE n.student_id = ?
    """, (student_id,)).fetchone()

    print(f"\n学生 {student_id}:")
    print(f"  笔记数: {notes['cnt']}")
    print(f"  分块数: {chunks['cnt']}")

    if chunks['cnt'] == 0 and notes['cnt'] > 0:
        print(f"  [警告] 有笔记但没有分块，检索会失败")

conn.close()
print("\n=== 诊断完成 ===")
