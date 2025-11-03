# 渲染架构图（在线 Kroki / 本地两种方式）

docs 目录内包含三份架构图文件：
- PlantUML 源：`docs/mcp-architecture.puml`
- Mermaid 源：`docs/mcp-architecture.mmd`
- PNG 预览：`docs/mcp-architecture.png`

可按以下方式重新生成 PNG（会覆盖同名文件）：

## 方案一：在线渲染（Kroki，最简单）

仅需 curl，适合 CI 或没有本地依赖的环境。

- PlantUML → PNG

    curl -sSf -X POST --data-binary @docs/mcp-architecture.puml \
      https://kroki.io/plantuml/png > docs/mcp-architecture.png

- Mermaid → PNG

    curl -sSf -X POST --data-binary @docs/mcp-architecture.mmd \
      https://kroki.io/mermaid/png > docs/mcp-architecture.png

若所在网络使用代理或被拦截，可改用方案二。

## 方案二：本地渲染（离线/可控）

### A) Mermaid CLI（推荐）
依赖 Node 与一个本地 Chrome（可用系统 Chrome 或 Chrome for Testing）。

1) 安装（跳过下载 Chromium）：

    export PUPPETEER_SKIP_DOWNLOAD=1
    npm i -g @mermaid-js/mermaid-cli@10.9.1

2) 准备 Puppeteer 配置（指定本机 Chrome 且关闭沙箱）：

    cat > docs/puppeteer.config.json << 'JSON'
    {"executablePath": "/path/to/chrome", "args": ["--no-sandbox","--disable-gpu","--disable-dev-shm-usage"]}
    JSON

3) 渲染：

    mmdc -i docs/mcp-architecture.mmd -o docs/mcp-architecture.png \
      -b transparent -s 1.2 -p docs/puppeteer.config.json

如遇中文标题解析报错，可将 Mermaid 的 `subgraph` 标题改为 ASCII 文本或英文引号包裹的标题。

### B) PlantUML（无需浏览器）
在没有 Java/Graphviz 的环境，可借助在线 PlantUML 服务器：

    curl -sSf -X POST --data-urlencode "text@docs/mcp-architecture.puml" \
      https://www.plantuml.com/plantuml/png > docs/mcp-architecture.png

或使用 Docker（完全离线）：

    docker run --rm -v "$PWD/docs":/ws \
      plantuml/plantuml -tpng /ws/mcp-architecture.puml -o /ws

> 提示：若需保留旧图，请更换输出文件名而非覆盖。
