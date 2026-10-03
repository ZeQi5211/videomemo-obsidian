import re


def _split_tag_items(tags_line: str) -> list[str]:
    """把 tags 行值部分切成标签列表（容错中文/英文逗号）。"""
    value = tags_line.split(":", 1)[1].strip().strip("[]").strip()
    if not value:
        return []
    parts = re.split(r"[，,、；;]", value)
    return [p.strip() for p in parts if p.strip()]


def _join_tag_items(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def _clean_tag_component(name: str) -> str:
    """清洗将作为标签组成部分的文本：/ [] 会破坏层级标签、逗号会破坏 YAML 数组、
    # 是标签注释符，统一替换为 ·；压缩连续空白；限制长度。"""
    name = re.sub(r"[/\\\[\]#,，、;；]", "·", name or "").strip()
    name = re.sub(r"\s+", " ", name)
    if len(name) > 30:
        name = name[:30].rstrip()
    return name


def extract_author_from_raw_info(raw_info: dict | None, platform: str = "") -> str:
    """从下载元信息中提取作者名（各平台字段不同）。

    返回清洗后的作者名；取不到返回空字符串（调用方据此决定是否加「作者/」标签）。
    清洗规则：去掉会破坏 Obsidian 层级标签/YAML 结构的字符（/ 空格 [] # 等）。
    """
    if not raw_info:
        return ""
    info = raw_info if isinstance(raw_info, dict) else {}
    author = ""
    p = (platform or "").lower()
    if p == "bilibili":
        author = str(info.get("uploader") or info.get("channel") or "").strip()
    elif p == "youtube":
        author = str(info.get("uploader") or info.get("channel") or "").strip()
    elif p == "douyin":
        author = str(info.get("author") or "").strip()
        if isinstance(info.get("author"), dict):
            author = str(info["author"].get("nickname") or "").strip()
    elif p == "kuaishou":
        a = info.get("author")
        if isinstance(a, dict):
            author = str(a.get("name") or "").strip()
        else:
            author = str(a or "").strip()
    else:
        # 通用兜底：优先常见字段
        for key in ("author", "uploader", "creator", "channel"):
            v = info.get(key)
            if isinstance(v, dict):
                v = v.get("name") or v.get("nickname") or ""
            if v:
                author = str(v).strip()
                break
    # 清洗：交给公共清洗函数（/ [] 破坏层级标签、逗号破坏 YAML 数组等）
    author = _clean_tag_component(author)
    return author


def inject_auto_tags(markdown: str | None, platform: str, author: str = "") -> str | None:
    """在 frontmatter 的 tags 数组里注入程序自动标签（不走模型，零错误）。

    - `平台/<platform>`：始终注入（platform 非空时）
    - `作者/<author>`：author 非空时注入（取不到作者就跳过）
    已有同名标签时不重复添加。只处理文档开头 frontmatter 块内的 tags 行；
    无 frontmatter / 无 tags 行时原样返回（不主动创建 frontmatter）。
    """
    if not markdown:
        return markdown
    platform = (platform or "").strip()
    if not platform:
        return markdown

    lines = markdown.split('\n')
    # 检测 frontmatter：首个非空行为 `---`，且其后存在闭合 `---`
    first_non_empty_idx = None
    for idx, line in enumerate(lines):
        if line.strip():
            first_non_empty_idx = idx
            break
    if first_non_empty_idx is None or lines[first_non_empty_idx].strip() != '---':
        return markdown
    close_idx = None
    for idx in range(first_non_empty_idx + 1, len(lines)):
        if lines[idx].strip() == '---':
            close_idx = idx
            break
    if close_idx is None:
        return markdown

    auto_tags = [f"平台/{platform}"]
    if author:
        auto_tags.append(f"作者/{_clean_tag_component(author)}")

    for idx in range(first_non_empty_idx + 1, close_idx):
        if lines[idx].strip().startswith('tags:') or lines[idx].strip().startswith('tag:'):
            items = _split_tag_items(lines[idx])
            existing = {item for item in items}
            added = [t for t in auto_tags if t not in existing]
            if added:
                # 保留原行的「tags:」前缀与冒号后的单个空格
                m = re.match(r'^(\s*tags?:)\s*', lines[idx])
                head = (m.group(1) if m else 'tags:') + ' '
                lines[idx] = head + _join_tag_items(items + added)
            break
    return '\n'.join(lines)


def normalize_frontmatter_tags(markdown: str | None) -> str | None:
    """规范化 frontmatter 中 `tags:` 行的分隔符，保证 YAML 数组被正确解析。

    LLM 在中文环境下经常把数组分隔符写成中文逗号/顿号/全角逗号
    （`tags: [A， B， C]`），YAML 会把整段 `[...]` 解析成一个巨大字符串标签，
    Obsidian 的层级标签（`主题/黄金`）全部失效。这里做代码兜底：
    只处理文档开头 frontmatter 块内的 tags 行，把 `，`、`、`、`；` 归一为
    英文逗号，并压缩逗号后多余空格（`A,  B` → `A, B`）。
    非 frontmatter / 无 tags 行的内容原样返回，不影响正文。
    """
    if not markdown:
        return markdown

    lines = markdown.split('\n')
    # 检测 frontmatter：首个非空行为 `---`，且其后存在闭合 `---`
    first_non_empty_idx = None
    for idx, line in enumerate(lines):
        if line.strip():
            first_non_empty_idx = idx
            break
    if first_non_empty_idx is None or lines[first_non_empty_idx].strip() != '---':
        return markdown

    close_idx = None
    for idx in range(first_non_empty_idx + 1, len(lines)):
        if lines[idx].strip() == '---':
            close_idx = idx
            break
    if close_idx is None:
        return markdown

    changed = False
    for idx in range(first_non_empty_idx + 1, close_idx):
        stripped = lines[idx].strip()
        if stripped.startswith('tags:') or stripped.startswith('tag:'):
            # 全角/中文标点 → 英文逗号；压缩逗号后的多余空格（",  " → ", "）
            new = lines[idx].replace('，', ',').replace('、', ',').replace('；', ',')
            new = re.sub(r',\s+', ', ', new)
            lines[idx] = new
            changed = True
            break
    if not changed:
        return markdown
    return '\n'.join(lines)


def prepend_source_link(markdown: str | None, source_url: str) -> str | None:
    """
    在笔记开头添加来源链接；若已存在来源链接则更新该行并避免重复。

    Obsidian 兼容规则：若笔记以 YAML frontmatter（`---` 开头且有闭合 `---`）开始，
    来源链接插入到 frontmatter 之后，保证 frontmatter 始终位于文件第 1 行，
    否则 Obsidian 不会把 frontmatter 识别为属性。无 frontmatter 时保持原逻辑（插最前）。
    """
    if markdown is None:
        return None

    source = (source_url or "").strip()
    if not source:
        return markdown

    header = f"> 来源链接：{source}"
    lines = markdown.splitlines()

    # 已存在来源链接（可能在 frontmatter 之后）：更新该行并返回，避免重复插入
    for idx, line in enumerate(lines):
        if line.strip().startswith(("> 来源链接：", "来源链接：")):
            lines[idx] = header
            return "\n".join(lines)

    # 检测 frontmatter：首个非空行为 `---`，且其后存在闭合 `---`
    first_non_empty_idx = None
    for idx, line in enumerate(lines):
        if line.strip():
            first_non_empty_idx = idx
            break

    if first_non_empty_idx is not None and lines[first_non_empty_idx].strip() == '---':
        close_idx = None
        for idx in range(first_non_empty_idx + 1, len(lines)):
            if lines[idx].strip() == '---':
                close_idx = idx
                break
        if close_idx is not None:
            # 插到闭合行之后（前面补一个空行分隔）
            insert_at = close_idx + 1
            new_lines = lines[:insert_at] + ["", header] + lines[insert_at:]
            return "\n".join(new_lines)

    if markdown.strip():
        return f"{header}\n\n{markdown}"
    return header


def normalize_toc(markdown: str | None) -> str | None:
    """规范化「## 目录」区块：剥掉目录条目里误带的 `#`/`##` 标题标记。

    LLM 有时把章节标题的 `##` 标记原样抄进目录列表（`- ## 1. xxx`），
    渲染出来和正文标题一样大。这里只做一件事：把目录区块内所有列表条目
    （含缩进子项）开头的标题标记剥掉——嵌套子项、加粗、链接等都允许，
    原样保留。没有目录区块时原样返回。
    """
    if not markdown:
        return markdown

    lines = markdown.split('\n')
    out = []
    in_toc = False
    for line in lines:
        stripped = line.strip()
        # 目录区块开始（容忍 #/##/### 任意级别写法，统一归一为 ##）
        if re.match(r'^#{1,6}\s*目录\s*$', stripped):
            in_toc = True
            out.append('## 目录')
            continue
        if in_toc:
            # 下一个标题出现，目录区块结束
            if re.match(r'^#{1,6}\s', stripped):
                in_toc = False
                out.append(line)
                continue
            m = re.match(r'^(\s*[-*+]\s+)(.*)$', line)
            if m:
                prefix, item = m.group(1), m.group(2)
                # 只剥条目开头的标题标记；兼容加粗包裹的写法（**## xxx** → **xxx**），
                # 缩进/加粗/其余内容全部原样保留
                item = re.sub(r'^(\*{0,2})\s*#{1,6}\s+', r'\1', item)
                out.append(prefix + item)
                continue
            # 目录区块内的空行 / 其他杂行原样保留
            out.append(line)
            continue
        out.append(line)
    return '\n'.join(out)


def build_timestamp_url(platform: str, video_id: str, total_seconds: int) -> str | None:
    """按平台拼接「跳转到第 total_seconds 秒」的视频链接。

    仅 B 站 / YouTube 支持可靠的时间戳跳转；抖音 / 快手 / 小红书等只能给出
    视频本身的链接（无时间参数）；无法识别的平台返回 None（调用方降级为纯文本）。
    """
    if platform == 'bilibili':
        # video_id 形如 BV1xxx 或 BV1xxx_p2（多 P）；_p 段转成查询参数
        if "_p" in video_id:
            bvid, _, page = video_id.partition("_p")
            return f"https://www.bilibili.com/video/{bvid}?p={page}&t={total_seconds}"
        return f"https://www.bilibili.com/video/{video_id}?t={total_seconds}"
    if platform == 'youtube':
        return f"https://www.youtube.com/watch?v={video_id}&t={total_seconds}s"
    if platform == 'douyin':
        return f"https://www.douyin.com/video/{video_id}"
    if platform == 'kuaishou':
        return f"https://www.kuaishou.com/short-video/{video_id}"
    if platform == 'xiaohongshu':
        return f"https://www.xiaohongshu.com/explore/{video_id}"
    return None


def replace_content_markers(markdown: str, video_id: str, platform: str = 'bilibili') -> str:
    """
    替换 *Content-04:16*、Content-04:16 或 Content-[04:16] 为超链接，跳转到对应平台视频的时间位置
    """
    # 匹配三种形式：*Content-04:16*、Content-04:16、Content-[04:16]
    pattern = r"(?:\*?)Content-(?:\[(\d{2}):(\d{2})\]|(\d{2}):(\d{2}))"

    def replacer(match):
        mm = match.group(1) or match.group(3)
        ss = match.group(2) or match.group(4)
        total_seconds = int(mm) * 60 + int(ss)

        url = build_timestamp_url(platform, video_id, total_seconds)
        if not url:
            # 平台无法拼出链接：降级为纯文本时间，不留下死链
            return f"({mm}:{ss})"
        return f"[原片 @ {mm}:{ss}]({url})"

    return re.sub(pattern, replacer, markdown)

