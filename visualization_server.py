#!/usr/bin/env python3
"""
Agent Memory System - 可视化文档Web服务

实时扫描项目结构，生成架构图、流程图、时序图等可视化文档。
每次刷新页面自动重新扫描，反映最新代码变更。

启动方式: python visualization_server.py
访问地址: http://localhost:8765
"""

import ast
import os
import re
import time
import html as html_mod
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
MEMORY_SYSTEM_ROOT = PROJECT_ROOT / "memory_system"


# ─────────────────────────────────────────────
# 项目扫描器
# ─────────────────────────────────────────────

def scan_project():
    """扫描项目结构，返回可视化数据"""
    data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "packages": {},
        "flat_modules": [],
        "total_files": 0,
        "total_classes": 0,
        "total_functions": 0,
    }

    if not MEMORY_SYSTEM_ROOT.exists():
        return data

    # 扫描子包
    subpackages = [d for d in MEMORY_SYSTEM_ROOT.iterdir()
                   if d.is_dir() and not d.name.startswith("_") and d.name != "__pycache__"]

    for pkg in sorted(subpackages):
        pkg_name = pkg.name
        pkg_data = {"modules": [], "classes": [], "functions": []}

        for py_file in sorted(pkg.glob("*.py")):
            if py_file.name.startswith("_") and py_file.name != "__init__.py":
                continue

            classes, functions, imports = parse_python_file(py_file)
            data["total_files"] += 1
            data["total_classes"] += len(classes)
            data["total_functions"] += len(functions)

            mod_info = {
                "name": py_file.stem,
                "file": py_file.name,
                "classes": classes,
                "functions": functions,
                "imports": imports,
            }
            pkg_data["modules"].append(mod_info)
            pkg_data["classes"].extend(classes)
            pkg_data["functions"].extend(functions)

        # 扫描子包中的子目录
        for sub_dir in sorted(pkg.iterdir()):
            if sub_dir.is_dir() and not sub_dir.name.startswith("_") and sub_dir.name != "__pycache__":
                for py_file in sorted(sub_dir.glob("*.py")):
                    if py_file.name.startswith("_") and py_file.name != "__init__.py":
                        continue
                    classes, functions, imports = parse_python_file(py_file)
                    data["total_files"] += 1
                    data["total_classes"] += len(classes)
                    data["total_functions"] += len(functions)
                    mod_info = {
                        "name": f"{sub_dir.name}/{py_file.stem}",
                        "file": f"{sub_dir.name}/{py_file.name}",
                        "classes": classes,
                        "functions": functions,
                        "imports": imports,
                    }
                    pkg_data["modules"].append(mod_info)
                    pkg_data["classes"].extend(classes)
                    pkg_data["functions"].extend(functions)

        data["packages"][pkg_name] = pkg_data

    # 扫描根目录的兼容别名模块
    for py_file in sorted(MEMORY_SYSTEM_ROOT.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        classes, functions, imports = parse_python_file(py_file)
        if not classes and not functions and imports:
            data["flat_modules"].append(py_file.stem)
            data["total_files"] += 1

    return data


def parse_python_file(filepath):
    """解析Python文件，提取类、函数和内部import"""
    classes = []
    functions = []
    imports = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception:
        return classes, functions, imports

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return classes, functions, imports

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if not node.name.startswith("_"):
                functions.append(node.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("memory_system."):
                for alias in node.names:
                    imports.append(node.module.replace("memory_system.", ""))

    return classes, functions, imports


# ─────────────────────────────────────────────
# Mermaid 图表生成
# ─────────────────────────────────────────────

def generate_architecture_mermaid(data):
    """生成架构图 - 模块依赖关系"""
    lines = ["graph TD"]

    # 子包节点
    pkg_colors = {
        "core": "sky",
        "processing": "teal",
        "storage": "mint",
        "infra": "amber",
        "observability": "violet",
        "api": "coral",
    }

    for pkg_name in sorted(data["packages"].keys()):
        color = pkg_colors.get(pkg_name, "slate")
        pkg = data["packages"][pkg_name]
        mod_count = len(pkg["modules"])
        cls_count = len(pkg["classes"])
        lines.append(f'    {pkg_name}["{pkg_name}<br/><small>{mod_count} modules / {cls_count} classes</small>"]')

    # AgentMemory 中心节点
    lines.append(f'    agent["AgentMemory<br/><small>Core Orchestrator</small>"]')

    # 依赖关系
    deps = {
        "agent": ["core"],
        "core": ["processing", "storage"],
        "storage": ["infra"],
        "api": ["core", "infra", "observability"],
    }

    for src, targets in deps.items():
        for tgt in targets:
            if tgt in data["packages"]:
                lines.append(f'    {src} --> {tgt}')

    return "\n".join(lines)


def generate_directory_mermaid(data):
    """生成目录结构图"""
    lines = ["graph LR"]

    total = data["total_files"]
    lines.append(f'    root["memory_system/<br/><small>{total} files</small>"]')

    for pkg_name in sorted(data["packages"].keys()):
        pkg = data["packages"][pkg_name]
        lines.append(f'    root --> {pkg_name}')
        mod_count = len(pkg["modules"])
        lines.append(f'    {pkg_name}["{pkg_name}/<br/><small>{mod_count} files</small>"]')

        for mod in pkg["modules"][:6]:
            safe_name = mod["name"].replace("/", "_")
            display = mod["name"].split("/")[-1]
            cls_count = len(mod["classes"])
            func_count = len(mod["functions"])
            cls_info = f'{cls_count}C' if cls_count else ""
            func_info = f'{func_count}F' if func_count else ""
            detail = " ".join(filter(None, [cls_info, func_info]))
            if detail:
                lines.append(f'    {pkg_name} --> {safe_name}["{display}<br/><small>{detail}</small>"]')
            else:
                lines.append(f'    {pkg_name} --> {safe_name}["{display}"]')

        if mod_count > 6:
            lines.append(f'    {pkg_name} --> {pkg_name}_more["... +{mod_count-6} more"]')

    return "\n".join(lines)


def generate_store_flow_mermaid():
    """生成记忆存储流程图"""
    return """flowchart TD
    A["User calls remember()"] --> B{"memory_type?"}
    B -->|fact| C["Store to Long-term Memory"]
    B -->|conversation| D["Store to Conversation History"]
    B -->|code| E["Store to Long-term Memory"]
    B -->|other| F["Store to Long-term Memory"]

    C --> G["Auto-build Knowledge Graph"]
    D --> H["Add to Interaction History"]
    E --> I["Store with metadata"]

    G --> J["KnowledgeGraph.add_entity()"]
    G --> K["KnowledgeGraph.add_relation()"]
    J --> L["Update Graph Storage"]
    K --> L

    H --> M["ShortTermMemory.add_interaction()"]
    H --> N["MemoryTable.log_interaction()"]

    I --> O["LongTermMemory.remember()"]
    O --> P["EmbeddingProvider.encode()"]
    P --> Q["VectorStore.add()"]
    Q --> R["MemoryRecord created"]

    L --> S["Return memory_id"]
    M --> S
    N --> S
    R --> S

    style A fill:#4DBBFF,stroke:#0B7BC1,color:#fff
    style S fill:#91DC18,stroke:#639B08,color:#fff
    style B fill:#F3B962,stroke:#DB901F,color:#311E02"""


def generate_recall_flow_mermaid():
    """生成记忆检索流程图"""
    return """flowchart TD
    A["User calls recall(query)"] --> B["Parse query parameters"]
    B --> C{"from_long_term?"}
    B --> D{"from_short_term?"}

    C -->|yes| E["LongTermMemory.recall()"]
    C -->|no| SKIP1["Skip long-term"]

    D -->|yes| F["Search working memory"]
    D -->|no| SKIP2["Skip short-term"]

    E --> G["VectorStore.search()"]
    G --> H["BM25 keyword search"]
    G --> I["Knowledge graph search"]
    H --> J["RRF fusion ranking"]
    I --> J
    J --> K["Apply filters"]
    K --> L["Apply exclude_sources"]

    F --> M["Tokenize query"]
    M --> N["Keyword overlap scoring"]
    N --> O["Return short-term hits"]

    L --> P["Merge results"]
    O --> P
    SKIP1 --> P
    SKIP2 --> P
    P --> Q["Sort by score"]
    Q --> R["Return top_k results"]

    style A fill:#4DBBFF,stroke:#0B7BC1,color:#fff
    style R fill:#91DC18,stroke:#639B08,color:#fff
    style J fill:#CA80FF,stroke:#9019E6,color:#fff"""


def generate_consolidation_flow_mermaid():
    """生成记忆巩固流程图"""
    return """flowchart TD
    A["Trigger consolidation"] --> B{"auto_consolidate?"}
    B -->|no| Z["Return skipped"]
    B -->|yes| C["Get working memory items"]

    C --> D{"importance >= threshold?"}
    D -->|yes| E["Copy to long-term memory"]
    D -->|no| F["Mark as skipped"]

    E --> G["Set metadata:<br/>consolidated_from=working_memory"]
    G --> H["Store in VectorStore"]

    F --> I["Keep in working memory"]

    H --> J["Cleanup phase"]
    J --> K{"item.importance >= threshold?"}
    K -->|yes| L["Remove from working memory"]
    K -->|no| M["Keep in working memory"]

    L --> N["Return consolidation stats"]
    M --> N

    style A fill:#4DBBFF,stroke:#0B7BC1,color:#fff
    style N fill:#91DC18,stroke:#639B08,color:#fff"""


def generate_api_sequence_mermaid():
    """生成API调用时序图"""
    return """sequenceDiagram
    participant U as User
    participant AM as AgentMemory
    participant STM as ShortTermMemory
    participant LTM as LongTermMemory
    participant VS as VectorStore
    participant EP as EmbeddingProvider
    participant KG as KnowledgeGraph
    participant SS as StructuredStore

    Note over U,SS: === remember() ===
    U->>AM: remember(content, memory_type="fact")
    AM->>LTM: remember(content, ...)
    LTM->>EP: encode(content)
    EP-->>LTM: embedding_vector
    LTM->>VS: add(content, vector)
    VS-->>LTM: memory_id
    LTM-->>AM: memory_id
    AM->>KG: build_knowledge_from_text(content)
    KG-->>AM: entities + relations
    AM-->>U: memory_id

    Note over U,SS: === recall() ===
    U->>AM: recall(query, top_k=5)
    AM->>LTM: recall(query, top_k=5)
    LTM->>EP: encode(query)
    EP-->>LTM: query_vector
    LTM->>VS: search(query_vector, top_k)
    VS-->>LTM: results
    LTM-->>AM: results
    AM->>STM: search_working_memory(query)
    STM-->>AM: short_term_results
    AM->>AM: merge + sort + truncate
    AM-->>U: top_k results

    Note over U,SS: === get_preference() ===
    U->>AM: get_preference(key)
    AM->>SS: get_preference(key)
    SS-->>AM: preference_dict
    AM-->>U: preference_dict"""


def generate_hybrid_search_sequence_mermaid():
    """生成混合搜索时序图"""
    return """sequenceDiagram
    participant U as User
    participant HSE as HybridSearchEngine
    participant VSS as VectorSearchStrategy
    participant KSS as KeywordSearchStrategy
    participant KGSS as KGSearchStrategy

    Note over U,KGSS: === Hybrid Search with RRF ===

    U->>HSE: search(query, top_k=10)

    par Parallel Strategies
        HSE->>VSS: search(query, top_k=10)
        VSS-->>HSE: vector_hits

        HSE->>KSS: search(query, top_k=10)
        KSS-->>HSE: keyword_hits

        HSE->>KGSS: search(query, top_k=10)
        KGSS-->>HSE: graph_hits
    end

    HSE->>HSE: RRF Fusion
    Note right of HSE: score = sum(1/(k+rank))

    HSE->>HSE: Deduplicate & sort
    HSE-->>U: fused_results"""


# ─────────────────────────────────────────────
# HTML 页面生成
# ─────────────────────────────────────────────

def generate_html(data):
    """生成完整的HTML页面"""

    arch_mermaid = generate_architecture_mermaid(data)
    dir_mermaid = generate_directory_mermaid(data)
    store_flow = generate_store_flow_mermaid()
    recall_flow = generate_recall_flow_mermaid()
    consolidation_flow = generate_consolidation_flow_mermaid()
    api_sequence = generate_api_sequence_mermaid()
    hybrid_sequence = generate_hybrid_search_sequence_mermaid()

    # 统计卡片
    pkg_count = len(data["packages"])
    stats_cards = ""
    stat_items = [
        ("文件总数", data["total_files"], "c-sky"),
        ("子包数量", pkg_count, "c-teal"),
        ("类定义数", data["total_classes"], "c-violet"),
        ("函数定义数", data["total_functions"], "c-amber"),
    ]
    for label, value, color in stat_items:
        stats_cards += f'<div class="stat-card"><div class="stat-value">{value}</div><div class="stat-label">{label}</div></div>\n'

    # 子包详情表格
    pkg_tables = ""
    pkg_desc = {
        "core": "核心记忆管理 - 短期/长期记忆、混合搜索、记忆巩固",
        "processing": "数据处理 - 嵌入、分词、知识图谱、压缩、去重",
        "storage": "存储层 - 向量存储、结构化存储、缓存、备份",
        "infra": "基础设施 - 限流、事件总线、断路器、配置、插件",
        "observability": "可观测性 - 遥测、审计、指标、健康检查、监控",
        "api": "API层 - FastAPI服务、CLI命令行、中间件栈",
    }
    for pkg_name in sorted(data["packages"].keys()):
        pkg = data["packages"][pkg_name]
        desc = pkg_desc.get(pkg_name, "")
        pkg_tables += f"""
        <details class="pkg-detail">
            <summary><span class="pkg-name">{pkg_name}/</span> <span class="pkg-desc">{desc}</span></summary>
            <table>
                <thead><tr><th>模块</th><th>类</th><th>函数</th></tr></thead>
                <tbody>"""
        for mod in pkg["modules"]:
            cls_str = ", ".join(mod["classes"][:4])
            if len(mod["classes"]) > 4:
                cls_str += f" +{len(mod['classes'])-4}"
            func_str = ", ".join(mod["functions"][:4])
            if len(mod["functions"]) > 4:
                func_str += f" +{len(mod['functions'])-4}"
            pkg_tables += f'<tr><td class="mod-name">{mod["name"]}</td><td class="cls-list">{cls_str or "-"}</td><td class="func-list">{func_str or "-"}</td></tr>\n'
        pkg_tables += "</tbody></table></details>\n"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Memory System - 可视化文档</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>
:root {{
    --bg: #f8f9fa;
    --card-bg: #ffffff;
    --text: #1a1a2e;
    --text-secondary: #6b7280;
    --border: #e5e7eb;
    --accent: #3b82f6;
    --accent-light: #eff6ff;
    --radius: 10px;
}}
@media (prefers-color-scheme: dark) {{
    :root {{
        --bg: #0f1117;
        --card-bg: #1a1d2e;
        --text: #e5e7eb;
        --text-secondary: #9ca3af;
        --border: #2d3348;
        --accent: #60a5fa;
        --accent-light: #1e293b;
    }}
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
header {{
    text-align: center;
    padding: 2rem 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 2rem;
}}
header h1 {{ font-size: 1.8rem; font-weight: 600; margin-bottom: 0.5rem; }}
header .subtitle {{ color: var(--text-secondary); font-size: 0.95rem; }}
header .timestamp {{ color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.5rem; }}
.stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
}}
.stat-card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.2rem;
    text-align: center;
}}
.stat-value {{ font-size: 2rem; font-weight: 600; color: var(--accent); }}
.stat-label {{ font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.25rem; }}
.section {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}}
.section h2 {{
    font-size: 1.2rem;
    font-weight: 600;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 0.5rem;
}}
.section h2 .icon {{ font-size: 1.1rem; }}
.mermaid {{
    display: flex;
    justify-content: center;
    padding: 1rem 0;
    overflow-x: auto;
}}
.mermaid svg {{ max-width: 100%; height: auto; }}
.pkg-detail {{
    margin-bottom: 0.5rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
}}
.pkg-detail summary {{
    padding: 0.75rem 1rem;
    cursor: pointer;
    background: var(--accent-light);
    font-weight: 500;
    font-size: 0.95rem;
}}
.pkg-detail summary:hover {{ opacity: 0.9; }}
.pkg-name {{ font-family: 'SF Mono', Monaco, monospace; color: var(--accent); }}
.pkg-desc {{ color: var(--text-secondary); font-size: 0.85rem; margin-left: 0.5rem; }}
.pkg-detail table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
}}
.pkg-detail th {{
    text-align: left;
    padding: 0.5rem 1rem;
    background: var(--accent-light);
    font-weight: 500;
    color: var(--text-secondary);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.pkg-detail td {{
    padding: 0.4rem 1rem;
    border-top: 1px solid var(--border);
}}
.mod-name {{ font-family: 'SF Mono', Monaco, monospace; font-size: 0.8rem; }}
.cls-list, .func-list {{ color: var(--text-secondary); font-size: 0.8rem; }}
.nav {{
    position: sticky;
    top: 0;
    background: var(--card-bg);
    border-bottom: 1px solid var(--border);
    padding: 0.5rem 2rem;
    z-index: 100;
    display: flex;
    gap: 1rem;
    overflow-x: auto;
    font-size: 0.85rem;
}}
.nav a {{
    color: var(--text-secondary);
    text-decoration: none;
    white-space: nowrap;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
}}
.nav a:hover {{ background: var(--accent-light); color: var(--accent); }}
footer {{
    text-align: center;
    padding: 2rem 0;
    color: var(--text-secondary);
    font-size: 0.8rem;
    border-top: 1px solid var(--border);
    margin-top: 2rem;
}}
</style>
</head>
<body>

<nav class="nav">
    <a href="#stats">统计概览</a>
    <a href="#architecture">架构图</a>
    <a href="#directory">目录结构</a>
    <a href="#store-flow">存储流程</a>
    <a href="#recall-flow">检索流程</a>
    <a href="#consolidation-flow">巩固流程</a>
    <a href="#api-sequence">API时序</a>
    <a href="#hybrid-search">混合搜索</a>
    <a href="#modules">模块详情</a>
</nav>

<div class="container">
    <header>
        <h1>Agent Memory System</h1>
        <div class="subtitle">可视化架构文档 - 实时生成</div>
        <div class="timestamp">最后更新: {data["timestamp"]}</div>
    </header>

    <div id="stats" class="section">
        <h2><span class="icon">&#128202;</span> 统计概览</h2>
        <div class="stats-grid">
            {stats_cards}
        </div>
    </div>

    <div id="architecture" class="section">
        <h2><span class="icon">&#127959;</span> 架构图 - 模块依赖关系</h2>
        <div class="mermaid">
{arch_mermaid}
        </div>
    </div>

    <div id="directory" class="section">
        <h2><span class="icon">&#128193;</span> 目录结构</h2>
        <div class="mermaid">
{dir_mermaid}
        </div>
    </div>

    <div id="store-flow" class="section">
        <h2><span class="icon">&#128229;</span> 流程图 - 记忆存储</h2>
        <div class="mermaid">
{store_flow}
        </div>
    </div>

    <div id="recall-flow" class="section">
        <h2><span class="icon">&#128270;</span> 流程图 - 记忆检索</h2>
        <div class="mermaid">
{recall_flow}
        </div>
    </div>

    <div id="consolidation-flow" class="section">
        <h2><span class="icon">&#128260;</span> 流程图 - 记忆巩固</h2>
        <div class="mermaid">
{consolidation_flow}
        </div>
    </div>

    <div id="api-sequence" class="section">
        <h2><span class="icon">&#9201;</span> 时序图 - API调用</h2>
        <div class="mermaid">
{api_sequence}
        </div>
    </div>

    <div id="hybrid-search" class="section">
        <h2><span class="icon">&#128269;</span> 时序图 - 混合搜索引擎</h2>
        <div class="mermaid">
{hybrid_sequence}
        </div>
    </div>

    <div id="modules" class="section">
        <h2><span class="icon">&#128736;</span> 模块详情</h2>
        {pkg_tables}
    </div>

    <footer>
        Agent Memory System v4.5 | Auto-generated documentation | Refresh page to update
    </footer>
</div>

<script>
mermaid.initialize({{
    startOnLoad: true,
    theme: 'default',
    securityLevel: 'loose',
    flowchart: {{ useMaxWidth: true, htmlLabels: true, curve: 'basis' }},
    sequence: {{ useMaxWidth: true, mirrorActors: false }}
}});
</script>
</body>
</html>"""


# ─────────────────────────────────────────────
# HTTP 服务器
# ─────────────────────────────────────────────

class VisualizationHandler(BaseHTTPRequestHandler):
    """处理可视化页面请求"""

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            data = scan_project()
            html = generate_html(data)
            content = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        print(f"  [HTTP] {args[0]}")


def main():
    port = 8765
    server = HTTPServer(("0.0.0.0", port), VisualizationHandler)

    print("=" * 60)
    print("  Agent Memory System - 可视化文档服务")
    print("=" * 60)
    print(f"  访问地址: http://localhost:{port}")
    print(f"  项目路径: {PROJECT_ROOT}")
    print(f"  每次刷新页面自动重新扫描项目结构")
    print("=" * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.server_close()


if __name__ == "__main__":
    main()
