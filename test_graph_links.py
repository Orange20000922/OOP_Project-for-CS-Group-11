"""测试 build_graph 能否正常返回边数组"""
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import tempfile
from pathlib import Path

from app.models.note import Note, NoteChunk
from app.services.knowledge_search_operations import KnowledgeSearchOperations
from app.storage.knowledge_tree_store import KnowledgeTreeStore
from app.storage.note_store import NoteStore


def make_note(i: int, student_id: str, course_id: str) -> Note:
    return Note(
        id=f"note_{i:03d}",
        student_id=student_id,
        course_id=course_id,
        filename=f"lecture_{i:02d}.md",
        file_type="md",
        title=f"第{i+1}讲",
    )


# 内容相似度高的分块（共享关键词，确保能产生边）
CHUNK_CONTENTS = [
    "操作系统进程调度算法，包括先来先服务FCFS和短作业优先SJF。",
    "进程调度中的优先级算法和时间片轮转RR算法，操作系统核心概念。",
    "内存管理分页机制，操作系统虚拟内存和页面置换算法。",
    "虚拟内存页面置换：LRU最近最少使用算法，内存管理策略。",
    "文件系统目录结构，操作系统磁盘调度算法SSTF和SCAN。",
    "磁盘调度SCAN算法与电梯算法，文件系统存储管理。",
    "死锁检测与预防，操作系统资源分配图和银行家算法。",
    "银行家算法安全序列，死锁避免策略，操作系统并发控制。",
]


def make_chunks(notes: list[Note]) -> list[NoteChunk]:
    chunks = []
    for i, note in enumerate(notes):
        content = CHUNK_CONTENTS[i % len(CHUNK_CONTENTS)]
        chunks.append(NoteChunk(
            chunk_id=f"{note.id}_c0",
            note_id=note.id,
            heading=f"第{i+1}节",
            content=content,
            chunk_index=0,
        ))
    return chunks


def run_test(label: str, notes: list[Note], chunks: list[NoteChunk],
             top_k: int, min_score: float, student_id: str, course_id: str,
             note_store: NoteStore, tree_store: KnowledgeTreeStore):
    search_ops = KnowledgeSearchOperations(
        note_store=note_store,
        tree_store=tree_store,
        memory=None,  # 强制走词法路径
    )
    graph = search_ops.build_graph(
        student_id=student_id,
        course_id=course_id,
        top_k=top_k,
        min_score=min_score,
    )
    status = "[OK]" if graph.links else "[FAIL]"
    print(f"\n{label}")
    print(f"  节点数: {graph.total_nodes}  边数: {graph.total_links}  {status}")
    for link in graph.links[:5]:
        print(f"    {link.source} -- {link.target}  score={link.value:.3f}")
    if len(graph.links) > 5:
        print(f"    ... 共 {len(graph.links)} 条边")
    return graph


def test_basic_links():
    print("\n=== 测试：基础边生成 ===")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        data_dir = Path(tmpdir)
        student_id = "stu_graph"
        course_id = "OS101"

        note_store = NoteStore(data_dir / "notes.db")
        tree_store = KnowledgeTreeStore(data_dir / "trees")

        notes = [make_note(i, student_id, course_id) for i in range(8)]
        chunks = make_chunks(notes)
        for note in notes:
            note_store.add_note(note)
        note_store.add_chunks(chunks)

        # 场景 1: 正常参数
        g1 = run_test("场景1: top_k=3, min_score=0.3", notes, chunks,
                      top_k=3, min_score=0.3, student_id=student_id,
                      course_id=course_id, note_store=note_store, tree_store=tree_store)
        assert g1.total_nodes == 8, f"节点数应为8，实际{g1.total_nodes}"
        assert g1.total_links > 0, "应该有边"

        # 场景 2: min_score 极低，边应该更多
        g2 = run_test("场景2: top_k=5, min_score=0.1", notes, chunks,
                      top_k=5, min_score=0.1, student_id=student_id,
                      course_id=course_id, note_store=note_store, tree_store=tree_store)
        assert g2.total_links >= g1.total_links, "更低阈值应产生更多或相等的边"

        # 场景 3: min_score 极高，边应该很少或为零
        g3 = run_test("场景3: top_k=3, min_score=0.99 (高阈值)", notes, chunks,
                      top_k=3, min_score=0.99, student_id=student_id,
                      course_id=course_id, note_store=note_store, tree_store=tree_store)
        print(f"  高阈值边数={g3.total_links} (预期极少)")

        # 场景 4: 验证边的 source/target 都是合法 chunk_id
        valid_ids = {c.chunk_id for c in chunks}
        for link in g1.links:
            assert link.source in valid_ids, f"source {link.source} 不在 chunk 集合中"
            assert link.target in valid_ids, f"target {link.target} 不在 chunk 集合中"
            assert link.source != link.target, "自环边"
            assert link.source < link.target, "边未规范化（source 应 <= target）"
        print("\n  [OK] 所有边的 source/target 合法，无自环，已规范化")

        # 场景 5: 边去重（同一对节点只有一条边）
        seen_pairs = set()
        for link in g1.links:
            pair = (link.source, link.target)
            assert pair not in seen_pairs, f"重复边: {pair}"
            seen_pairs.add(pair)
        print(f"  [OK] 无重复边，共 {len(seen_pairs)} 条唯一边")

    print("\n=== 基础边生成测试通过 ===")


def test_single_note():
    print("\n=== 测试：单笔记（无法产生边）===")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        data_dir = Path(tmpdir)
        student_id = "stu_single"
        course_id = "OS101"

        note_store = NoteStore(data_dir / "notes.db")
        tree_store = KnowledgeTreeStore(data_dir / "trees")

        note = make_note(0, student_id, course_id)
        note_store.add_note(note)
        note_store.add_chunks([NoteChunk(
            chunk_id="note_000_c0", note_id=note.id,
            heading="唯一分块", content="只有一个分块，无法产生边。",
            chunk_index=0,
        )])

        search_ops = KnowledgeSearchOperations(
            note_store=note_store, tree_store=tree_store, memory=None
        )
        graph = search_ops.build_graph(student_id=student_id, course_id=course_id)
        assert graph.total_nodes == 1
        assert graph.total_links == 0
        print(f"  [OK] 单节点图：节点={graph.total_nodes}，边={graph.total_links}")

    print("=== 单笔记测试通过 ===")


def test_empty_notes():
    print("\n=== 测试：无笔记（空图）===")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        data_dir = Path(tmpdir)
        student_id = "stu_empty"
        course_id = "OS101"

        note_store = NoteStore(data_dir / "notes.db")
        tree_store = KnowledgeTreeStore(data_dir / "trees")

        search_ops = KnowledgeSearchOperations(
            note_store=note_store, tree_store=tree_store, memory=None
        )
        graph = search_ops.build_graph(student_id=student_id, course_id=course_id)
        assert graph.total_nodes == 0
        assert graph.total_links == 0
        print(f"  [OK] 空图：节点={graph.total_nodes}，边={graph.total_links}")

    print("=== 空图测试通过 ===")


def test_graph_response_serializable():
    print("\n=== 测试：GraphResponse 可序列化为 JSON ===")
    import json
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        data_dir = Path(tmpdir)
        student_id = "stu_serial"
        course_id = "OS101"

        note_store = NoteStore(data_dir / "notes.db")
        tree_store = KnowledgeTreeStore(data_dir / "trees")

        notes = [make_note(i, student_id, course_id) for i in range(4)]
        chunks = make_chunks(notes)
        for note in notes:
            note_store.add_note(note)
        note_store.add_chunks(chunks)

        search_ops = KnowledgeSearchOperations(
            note_store=note_store, tree_store=tree_store, memory=None
        )
        graph = search_ops.build_graph(
            student_id=student_id, course_id=course_id, top_k=3, min_score=0.2
        )

        payload = graph.model_dump()
        json_str = json.dumps(payload, ensure_ascii=False)
        parsed = json.loads(json_str)

        assert len(parsed["nodes"]) == graph.total_nodes
        assert len(parsed["links"]) == graph.total_links
        print(f"  [OK] 序列化成功：{graph.total_nodes} 节点，{graph.total_links} 边")
        if parsed["links"]:
            print(f"  示例边: {parsed['links'][0]}")

    print("=== 序列化测试通过 ===")


if __name__ == "__main__":
    test_basic_links()
    test_single_note()
    test_empty_notes()
    test_graph_response_serializable()
    print("\n全部测试完成")
