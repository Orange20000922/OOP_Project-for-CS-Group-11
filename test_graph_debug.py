"""调试图谱边渲染问题的测试脚本"""
import asyncio
import json
from playwright.async_api import async_playwright


async def test_graph_links():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 启用控制台日志
        page.on("console", lambda msg: print(f"[Browser Console] {msg.type}: {msg.text}"))

        # 先访问登录页
        await page.goto("http://localhost:8000/")
        await page.wait_for_timeout(1000)

        # 登录
        try:
            await page.wait_for_selector('input[placeholder*="学号"]', timeout=3000)
            await page.fill('input[placeholder*="学号"]', 'manual_e2e_001')
            await page.fill('input[type="password"]', 'test123')
            await page.click('button:has-text("登录")')
            await page.wait_for_timeout(2000)
            print("登录成功")
        except Exception as e:
            print(f"登录失败或已登录: {e}")

        # 访问知识工作台
        await page.goto("http://localhost:8000/knowledge-workspace")
        await page.wait_for_selector("#knowledge-app", timeout=10000)

        # 等待图谱加载
        await page.wait_for_timeout(3000)

        # 获取图谱数据
        graph_data = await page.evaluate("""
            () => {
                const app = document.querySelector('#knowledge-app').__vue__;
                return {
                    nodes: app.graphData.nodes.length,
                    links: app.graphData.links.length,
                    linksDetail: app.graphData.links,
                    total_nodes: app.graphData.total_nodes,
                    total_links: app.graphData.total_links,
                };
            }
        """)

        print("\n=== 图谱数据检查 ===")
        print(f"节点数量: {graph_data['nodes']}")
        print(f"边数量: {graph_data['links']}")
        print(f"total_nodes: {graph_data['total_nodes']}")
        print(f"total_links: {graph_data['total_links']}")
        print(f"\n边详情:")
        print(json.dumps(graph_data['linksDetail'], indent=2, ensure_ascii=False))

        # 检查 Cytoscape 实例
        cy_info = await page.evaluate("""
            () => {
                const app = document.querySelector('#knowledge-app').__vue__;
                if (!app.graphRenderer) {
                    return { error: 'No graphRenderer' };
                }
                // 尝试访问 cytoscape 实例（可能需要调整）
                return {
                    hasRenderer: true,
                };
            }
        """)
        print(f"\nCytoscape 渲染器: {cy_info}")

        # 截图
        await page.screenshot(path="graph_debug.png")
        print("\n截图已保存到 graph_debug.png")

        await page.wait_for_timeout(5000)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_graph_links())
