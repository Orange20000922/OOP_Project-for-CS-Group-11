"""知识树模块多主题多文件稳定性测试"""
import sys
import tempfile
from pathlib import Path

# Windows GBK 终端兼容
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OK = "[OK]"
FAIL = "[FAIL]"

from app.models.knowledge import KnowledgeTree, KnowledgeTopic
from app.models.note import Note, NoteChunk
from app.services.knowledge_tree_operations import KnowledgeTreeOperations
from app.storage.knowledge_tree_store import KnowledgeTreeStore
from app.storage.note_store import NoteStore


def make_note(i: int, student_id: str, course_id: str = "CS101") -> Note:
    return Note(
        id=f"note_{i:03d}",
        student_id=student_id,
        course_id=course_id,
        filename=f"lecture_{i:02d}.md",
        file_type="md",
        title=f"第{i+1}讲",
        summary=f"主题{i % 3}相关内容",
    )


def make_chunk(note: Note, j: int) -> NoteChunk:
    return NoteChunk(
        chunk_id=f"{note.id}_chunk_{j}",
        note_id=note.id,
        heading=f"小节 {j+1}",
        content=f"{note.summary}，第{j+1}分块详细内容。",
        chunk_index=j,
    )


def make_topic(
    topic_id: str,
    name: str,
    note_ids: list[str],
    parent_id: str | None = None,
    child_ids: list[str] | None = None,
) -> KnowledgeTopic:
    return KnowledgeTopic(
        id=topic_id,
        name=name,
        note_ids=note_ids,
        parent_id=parent_id,
        child_ids=child_ids or [],
    )


def test_multi_topic_multi_note():
    print("\n=== 测试：多主题多笔记 ===")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        data_dir = Path(tmpdir)
        student_id = "stu_001"
        course_id = "CS101"

        note_store = NoteStore(data_dir / "notes.db")
        tree_store = KnowledgeTreeStore(data_dir / "trees")
        tree_ops = KnowledgeTreeOperations(note_store, tree_store)

        # 15 个笔记，每个 3 个分块
        notes = [make_note(i, student_id, course_id) for i in range(15)]
        for note in notes:
            note_store.add_note(note)
            note_store.add_chunks([make_chunk(note, j) for j in range(3)])
        print(f"保存了 {len(notes)} 个笔记，{len(notes)*3} 个分块")

        # 3 个顶层主题，每个 5 个笔记
        tree = KnowledgeTree(student_id=student_id, course_id=course_id)
        for i in range(3):
            nids = [f"note_{j:03d}" for j in range(i * 5, (i + 1) * 5)]
            t = make_topic(f"topic_{i}", f"主题{i}", nids)
            tree.topics[t.id] = t
            tree.root_ids.append(t.id)
            print(f"  topic_{i}: {nids}")

        # topic_1 下挂两个子主题
        tree.topics["topic_1"].child_ids = ["topic_1a", "topic_1b"]
        tree.topics["topic_1a"] = make_topic(
            "topic_1a", "主题1-A", ["note_005", "note_006"], parent_id="topic_1"
        )
        tree.topics["topic_1b"] = make_topic(
            "topic_1b", "主题1-B", ["note_007", "note_008"], parent_id="topic_1"
        )
        tree_store.save(tree)

        # --- 测试 1: 各顶层主题笔记收集 ---
        print("\n--- 测试 1: 顶层主题笔记收集 ---")
        for i in range(3):
            ids = tree_ops.collect_topic_note_ids(tree, f"topic_{i}")
            print(f"  topic_{i}: {len(ids)} 个 -> {sorted(ids)}")

        # --- 测试 2: 含子主题的递归收集 ---
        print("\n--- 测试 2: topic_1 含子主题递归收集 ---")
        all_1 = tree_ops.collect_topic_note_ids(tree, "topic_1")
        expected = (
            set(tree.topics["topic_1"].note_ids)
            | set(tree.topics["topic_1a"].note_ids)
            | set(tree.topics["topic_1b"].note_ids)
        )
        assert all_1 == expected, f"期望 {expected}，实际 {all_1}"
        print(f"  [OK]收集到 {len(all_1)} 个笔记: {sorted(all_1)}")

        # --- 测试 3: 不存在的主题 ---
        print("\n--- 测试 3: 不存在的主题 ---")
        empty = tree_ops.collect_topic_note_ids(tree, "topic_999")
        assert len(empty) == 0
        print("  [OK]返回空集合")

        # --- 测试 4: 持久化一致性 ---
        print("\n--- 测试 4: 持久化一致性 ---")
        loaded = tree_store.load(student_id, course_id)
        assert len(loaded.topics) == len(tree.topics), "主题数量不一致"
        for tid, orig in tree.topics.items():
            ld = loaded.topics[tid]
            assert orig.name == ld.name, f"{tid} name 不一致"
            assert set(orig.note_ids) == set(ld.note_ids), f"{tid} note_ids 不一致"
            assert orig.parent_id == ld.parent_id, f"{tid} parent_id 不一致"
            assert set(orig.child_ids) == set(ld.child_ids), f"{tid} child_ids 不一致"
        print(f"  [OK]{len(loaded.topics)} 个主题数据一致")

        # --- 测试 5: 笔记存在性验证 ---
        print("\n--- 测试 5: 笔记存在性验证 ---")
        missing = []
        for tid, topic in tree.topics.items():
            for nid in topic.note_ids:
                if note_store.get_note(nid) is None:
                    missing.append((tid, nid))
        if missing:
            print(f"  [FAIL]{len(missing)} 个缺失笔记: {missing}")
        else:
            print("  [OK]所有引用笔记均存在")

    print("\n=== 多主题多笔记测试通过 ===")


def test_edge_cases():
    print("\n=== 测试：边界情况 ===")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        data_dir = Path(tmpdir)
        student_id = "stu_002"
        course_id = "CS102"

        note_store = NoteStore(data_dir / "notes.db")
        tree_store = KnowledgeTreeStore(data_dir / "trees")
        tree_ops = KnowledgeTreeOperations(note_store, tree_store)

        # 边界 1: 空知识树
        print("\n--- 边界 1: 空知识树 ---")
        empty_tree = KnowledgeTree(student_id=student_id, course_id=course_id)
        tree_store.save(empty_tree)
        loaded = tree_store.load(student_id, course_id)
        assert len(loaded.topics) == 0
        print("  [OK]空知识树正常")

        # 边界 2: 主题无笔记
        print("\n--- 边界 2: 主题无笔记 ---")
        t = make_topic("t_empty", "空主题", [])
        empty_tree.topics[t.id] = t
        empty_tree.root_ids.append(t.id)
        ids = tree_ops.collect_topic_note_ids(empty_tree, "t_empty")
        assert len(ids) == 0
        print("  [OK]空主题返回空集合")

        # 边界 3: 5 层深度嵌套
        print("\n--- 边界 3: 5 层深度嵌套 ---")
        deep_tree = KnowledgeTree(student_id=student_id, course_id=course_id)
        parent_id = None
        for i in range(5):
            tid = f"level_{i}"
            t = make_topic(tid, f"层级{i}", [f"note_l{i}"], parent_id=parent_id)
            deep_tree.topics[tid] = t
            if parent_id:
                deep_tree.topics[parent_id].child_ids.append(tid)
            else:
                deep_tree.root_ids.append(tid)
            parent_id = tid

        all_deep = tree_ops.collect_topic_note_ids(deep_tree, "level_0")
        assert len(all_deep) == 5, f"期望 5，实际 {len(all_deep)}"
        print(f"  [OK]5 层嵌套收集到 {len(all_deep)} 个笔记: {sorted(all_deep)}")

        # 边界 4: 循环引用（seen 集合保护）
        print("\n--- 边界 4: 循环引用保护 ---")
        circ_tree = KnowledgeTree(student_id=student_id, course_id=course_id)
        circ_tree.topics["ca"] = make_topic("ca", "A", ["note_a"], child_ids=["cb"])
        circ_tree.topics["cb"] = make_topic("cb", "B", ["note_b"], parent_id="ca", child_ids=["ca"])
        circ_tree.root_ids.append("ca")
        try:
            ids = tree_ops.collect_topic_note_ids(circ_tree, "ca")
            print(f"  [OK]循环引用被截断，收集到 {len(ids)} 个笔记: {sorted(ids)}")
        except RecursionError:
            print("  [FAIL]循环引用导致递归溢出")

        # 边界 5: 100 个主题持久化
        print("\n--- 边界 5: 100 个主题持久化 ---")
        big_tree = KnowledgeTree(student_id=student_id, course_id=course_id)
        for i in range(100):
            tid = f"big_{i:03d}"
            t = make_topic(tid, f"大主题{i}", [f"big_note_{i}"])
            big_tree.topics[tid] = t
            big_tree.root_ids.append(tid)
        tree_store.save(big_tree)
        loaded_big = tree_store.load(student_id, course_id)
        assert len(loaded_big.topics) == 100
        print("  [OK]100 个主题持久化/加载正常")

    print("\n=== 边界情况测试通过 ===")


if __name__ == "__main__":
    test_multi_topic_multi_note()
    test_edge_cases()
    print("\n✓ 全部测试完成")
