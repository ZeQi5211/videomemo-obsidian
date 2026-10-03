import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "utils" / "note_helper.py"
spec = importlib.util.spec_from_file_location("note_helper", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("note_helper module spec not found")
note_helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(note_helper)


class TestNoteHelper(unittest.TestCase):
    def test_prepend_source_link_adds_header_at_top(self):
        source_url = "https://www.bilibili.com/video/BV1xx411c7mD"
        markdown = "## 标题\n\n内容"

        result = note_helper.prepend_source_link(markdown, source_url)

        self.assertTrue(result.startswith(f"> 来源链接：{source_url}\n\n"))
        self.assertIn("## 标题", result)

    def test_prepend_source_link_does_not_duplicate_when_header_exists(self):
        source_url = "https://www.youtube.com/watch?v=abc123"
        markdown = f"> 来源链接：{source_url}\n\n## 标题\n\n内容"

        result = note_helper.prepend_source_link(markdown, source_url)

        self.assertEqual(result, markdown)

    def test_prepend_source_link_after_frontmatter(self):
        source_url = "https://www.bilibili.com/video/BV1xx411c7mD"
        markdown = (
            '---\n'
            'title: "「测试」深度精读笔记"\n'
            'type: video\n'
            '---\n'
            '\n'
            '**一句话核心概括**\n'
        )

        result = note_helper.prepend_source_link(markdown, source_url)

        lines = result.splitlines()
        # frontmatter 仍位于文件最开头
        self.assertEqual(lines[0].strip(), '---')
        # 来源链接插在闭合 ---（第二个）之后
        dashes = [i for i, l in enumerate(lines) if l.strip() == '---']
        close_idx = dashes[1]
        self.assertEqual(lines[close_idx + 1].strip(), '')
        self.assertEqual(lines[close_idx + 2], f'> 来源链接：{source_url}')
        # 正文在后
        self.assertIn('**一句话核心概括**', result)

    def test_prepend_source_link_updates_header_inside_frontmatter_note(self):
        """来源链接已存在（位于 frontmatter 之后）时更新该行而不重复插入。"""
        source_url = "https://www.bilibili.com/video/BV1new"
        markdown = (
            '---\n'
            'title: "「测试」深度精读笔记"\n'
            '---\n'
            '\n'
            f'> 来源链接：https://www.bilibili.com/video/BV1old\n'
            '\n'
            '正文'
        )

        result = note_helper.prepend_source_link(markdown, source_url)

        self.assertNotIn('BV1old', result)
        self.assertIn(f'> 来源链接：{source_url}', result)
        # frontmatter 依然在最前，来源链接仍在其后
        lines = result.splitlines()
        close_idx = next(i for i, l in enumerate(lines) if l.strip() == '---')
        self.assertLess(close_idx, next(i for i, l in enumerate(lines) if '来源链接' in l))

    def test_normalize_toc_strips_heading_markers_in_items(self):
        markdown = "## 目录\n\n- ## 1. 章节一\n- ## 2. 章节二\n\n## 1. 章节一\n正文"

        result = note_helper.normalize_toc(markdown)

        self.assertIn("- 1. 章节一", result)
        self.assertIn("- 2. 章节二", result)
        self.assertNotIn("- ## ", result)
        # 正文标题不受影响
        self.assertIn("\n## 1. 章节一\n", result)

    def test_normalize_toc_strips_heading_marker_inside_bold(self):
        markdown = "## 目录\n\n- **## 4. 应用矩阵**\n\n## 4. 应用矩阵\n正文"

        result = note_helper.normalize_toc(markdown)

        # 加粗保留，只剥标题标记
        self.assertIn("- **4. 应用矩阵**", result)

    def test_normalize_toc_keeps_sub_items_and_strips_their_markers(self):
        markdown = (
            "## 目录\n\n"
            "- 章节一\n"
            "  - 子项A\n"
            "  - ## 子项B\n"
            "- 章节二\n\n"
            "## 章节一\n正文"
        )

        result = note_helper.normalize_toc(markdown)

        # 嵌套子项允许、缩进保留；子项里的标题标记同样剥掉
        self.assertIn("  - 子项A", result)
        self.assertIn("  - 子项B", result)
        self.assertNotIn("- ## 子项B", result)
        self.assertIn("- 章节一", result)
        self.assertIn("- 章节二", result)

    def test_normalize_toc_noop_without_toc_section(self):
        markdown = "# 标题\n\n- 普通列表 ## 不该被动\n正文"

        self.assertEqual(note_helper.normalize_toc(markdown), markdown)
        self.assertIsNone(note_helper.normalize_toc(None))

    def test_normalize_frontmatter_tags_cn_commas_to_en(self):
        """中文逗号/顿号/全角逗号 → 英文逗号，层级标签才能被 YAML 正确解析"""
        markdown = (
            '---\n'
            'title: "「测试」深度精读笔记"\n'
            'tags: [笔记类型/精读， 笔记类型/视频笔记， 主题/黄金、 主题/地缘政治； 主题/美联储]\n'
            'summary: "一句话"\n'
            '---\n'
            '\n'
            '正文'
        )
        result = note_helper.normalize_frontmatter_tags(markdown)
        self.assertIn(
            'tags: [笔记类型/精读, 笔记类型/视频笔记, 主题/黄金, 主题/地缘政治, 主题/美联储]',
            result,
        )
        self.assertNotIn('，', result.split('---')[1])
        self.assertNotIn('、', result.split('---')[1])
        self.assertNotIn('；', result.split('---')[1])
        # 正文不受影响
        self.assertIn('正文', result)

    def test_normalize_frontmatter_tags_noop_when_already_en(self):
        markdown = (
            '---\n'
            'tags: [笔记类型/精读, 主题/黄金]\n'
            '---\n'
            '\n'
            '正文'
        )
        self.assertEqual(note_helper.normalize_frontmatter_tags(markdown), markdown)

    def test_normalize_frontmatter_tags_noop_without_frontmatter(self):
        markdown = '正文，含中文逗号，但没有 frontmatter'
        self.assertEqual(note_helper.normalize_frontmatter_tags(markdown), markdown)
        self.assertIsNone(note_helper.normalize_frontmatter_tags(None))

    def test_normalize_frontmatter_tags_does_not_touch_body_commas(self):
        """frontmatter 之外正文里的中文逗号保持不变"""
        markdown = (
            '---\n'
            'tags: [主题/黄金， 主题/地缘政治]\n'
            '---\n'
            '\n'
            '正文里的中文逗号，原样保留。'
        )
        result = note_helper.normalize_frontmatter_tags(markdown)
        self.assertIn('正文里的中文逗号，原样保留。', result)
        self.assertIn('tags: [主题/黄金, 主题/地缘政治]', result)

    def test_inject_auto_tags_adds_platform_and_author(self):
        markdown = (
            '---\n'
            'tags: [笔记类型/精读, 主题/黄金]\n'
            '---\n'
            '\n'
            '正文'
        )
        result = note_helper.inject_auto_tags(markdown, platform="bilibili", author="某UP主")
        self.assertIn('平台/bilibili', result)
        self.assertIn('作者/某UP主', result)
        # 原有标签保留，顺序：原有 + 新增
        self.assertIn('tags: [笔记类型/精读, 主题/黄金, 平台/bilibili, 作者/某UP主]', result)

    def test_inject_auto_tags_skips_when_author_empty(self):
        markdown = (
            '---\n'
            'tags: [笔记类型/精读]\n'
            '---\n'
            '\n'
            '正文'
        )
        result = note_helper.inject_auto_tags(markdown, platform="bilibili", author="")
        self.assertIn('平台/bilibili', result)
        self.assertNotIn('作者/', result)

    def test_inject_auto_tags_no_duplicate(self):
        markdown = (
            '---\n'
            'tags: [笔记类型/精读, 平台/bilibili, 作者/某UP主]\n'
            '---\n'
            '\n'
            '正文'
        )
        result = note_helper.inject_auto_tags(markdown, platform="bilibili", author="某UP主")
        self.assertEqual(result, markdown)

    def test_inject_auto_tags_cleans_author_special_chars(self):
        """作者名里的 /、[] 会破坏层级标签 / YAML 数组，必须清洗"""
        result = note_helper.inject_auto_tags(
            '---\ntags: [笔记类型/精读]\n---\n\n正文',
            platform="youtube",
            author="John / Doe [TV]",
        )
        self.assertIn('作者/John · Doe ·TV·', result)
        self.assertNotIn('/', result.split('作者/')[1].strip(']').strip())

    def test_extract_author_from_raw_info_platforms(self):
        # B 站 / YouTube：yt-dlp 的 uploader
        self.assertEqual(
            note_helper.extract_author_from_raw_info({"uploader": "某UP主"}, "bilibili"),
            "某UP主",
        )
        # 抖音：author 昵称（字符串）
        self.assertEqual(
            note_helper.extract_author_from_raw_info({"author": "某博主"}, "douyin"),
            "某博主",
        )
        # 抖音：author 为 dict
        self.assertEqual(
            note_helper.extract_author_from_raw_info({"author": {"nickname": "某博主"}}, "douyin"),
            "某博主",
        )
        # 快手：author.name
        self.assertEqual(
            note_helper.extract_author_from_raw_info({"author": {"name": "某作者"}}, "kuaishou"),
            "某作者",
        )
        # 空/未知 → 空字符串
        self.assertEqual(note_helper.extract_author_from_raw_info(None, "bilibili"), "")
        self.assertEqual(note_helper.extract_author_from_raw_info({}, "bilibili"), "")


if __name__ == "__main__":
    unittest.main()
