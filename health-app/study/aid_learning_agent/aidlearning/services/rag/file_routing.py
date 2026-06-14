"""
文件类型路由器
==============

RAG 管线的集中式文件类型分类和路由。
确定每种文档类型的适当处理方法。
"""

from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """文档类型分类。"""

    PDF = "pdf"
    TEXT = "text"
    MARKDOWN = "markdown"
    DOCX = "docx"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    IMAGE = "image"
    UNKNOWN = "unknown"


@dataclass
class FileClassification:
    """文件分类结果。"""

    parser_files: List[str]
    text_files: List[str]
    image_files: List[str]
    unsupported: List[str]


class FileTypeRouter:
    """RAG 管线的文件类型路由器。

    在处理前对文件进行分类，将其路由到适当的处理器：
    - PDF / Office 文件 -> 基于解析器的文本提取
    - 文本文件 -> 直接读取（快速、简单）
    - 不支持 -> 跳过并警告
    """

    PDF_EXTENSIONS = {".pdf"}
    OFFICE_EXTENSIONS = {".docx", ".xlsx", ".pptx"}
    PARSER_EXTENSIONS = PDF_EXTENSIONS | OFFICE_EXTENSIONS

    TEXT_EXTENSIONS = {
        # 纯文本和文档
        ".txt",
        ".text",
        ".log",
        ".md",
        ".markdown",
        ".rst",
        ".asciidoc",
        # 数据/配置
        ".json",
        ".jsonc",
        ".json5",
        ".yaml",
        ".yml",
        ".toml",
        ".csv",
        ".tsv",
        ".ini",
        ".cfg",
        ".conf",
        ".env",
        ".properties",
        # 排版
        ".tex",
        ".latex",
        ".bib",
        # JavaScript / TypeScript 系列
        ".js",
        ".mjs",
        ".cjs",
        ".ts",
        ".mts",
        ".cts",
        ".jsx",
        ".tsx",
        # Web 框架
        ".vue",
        ".svelte",
        # Python
        ".py",
        # JVM 语言
        ".java",
        ".kt",
        ".kts",
        ".scala",
        ".groovy",
        ".gradle",
        # 系统语言
        ".c",
        ".h",
        ".cpp",
        ".cc",
        ".cxx",
        ".hpp",
        ".hh",
        ".hxx",
        ".cs",
        ".go",
        ".rs",
        ".zig",
        ".nim",
        # Apple 平台
        ".swift",
        ".m",
        ".mm",
        # 脚本语言
        ".rb",
        ".php",
        ".pl",
        ".pm",
        ".lua",
        ".r",
        ".jl",
        ".dart",
        # 函数式语言
        ".hs",
        ".clj",
        ".cljs",
        ".cljc",
        ".ex",
        ".exs",
        ".erl",
        ".ml",
        ".mli",
        ".fs",
        ".fsx",
        ".lisp",
        ".lsp",
        ".scm",
        ".rkt",
        # Web 标记/样式
        ".html",
        ".htm",
        ".xml",
        ".svg",
        ".css",
        ".scss",
        ".sass",
        ".less",
        # 智能合约
        ".sol",
        # Shell/编辑器
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".ps1",
        ".vim",
        # 查询/IDL
        ".sql",
        ".graphql",
        ".gql",
        ".proto",
        # 构建/基础设施
        ".cmake",
        ".mk",
        ".tf",
        ".hcl",
        ".nginxconf",
        ".dockerfile",
    }

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif"}

    @classmethod
    def get_document_type(cls, file_path: str) -> DocumentType:
        """按类型对单个文件进行分类。"""
        ext = Path(file_path).suffix.lower()

        if ext in cls.PDF_EXTENSIONS:
            return DocumentType.PDF
        elif ext in cls.TEXT_EXTENSIONS:
            return DocumentType.TEXT
        elif ext == ".docx":
            return DocumentType.DOCX
        elif ext == ".xlsx":
            return DocumentType.SPREADSHEET
        elif ext == ".pptx":
            return DocumentType.PRESENTATION
        elif ext in cls.IMAGE_EXTENSIONS:
            return DocumentType.IMAGE
        else:
            if cls._is_text_file(file_path):
                return DocumentType.TEXT
            return DocumentType.UNKNOWN

    @classmethod
    def _is_text_file(cls, file_path: str, sample_size: int = 8192) -> bool:
        """通过检查文件内容来检测是否为文本文件。"""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(sample_size)

            if b"\x00" in chunk:
                return False

            chunk.decode("utf-8")
            return True
        except (UnicodeDecodeError, IOError, OSError):
            return False

    @classmethod
    def classify_files(cls, file_paths: List[str]) -> FileClassification:
        """按处理方法对文件列表进行分类。"""
        parser_files = []
        text_files = []
        image_files = []
        unsupported = []

        for path in file_paths:
            doc_type = cls.get_document_type(path)

            if doc_type in (
                DocumentType.PDF,
                DocumentType.DOCX,
                DocumentType.SPREADSHEET,
                DocumentType.PRESENTATION,
            ):
                parser_files.append(path)
            elif doc_type in (DocumentType.TEXT, DocumentType.MARKDOWN):
                text_files.append(path)
            elif doc_type == DocumentType.IMAGE:
                image_files.append(path)
            else:
                unsupported.append(path)

        logger.debug(
            f"Classified {len(file_paths)} files: "
            f"{len(parser_files)} parser, {len(text_files)} text, "
            f"{len(image_files)} image, {len(unsupported)} unsupported"
        )

        return FileClassification(
            parser_files=parser_files,
            text_files=text_files,
            image_files=image_files,
            unsupported=unsupported,
        )

    TEXT_DECODING_CANDIDATES = (
        "utf-8",
        "utf-8-sig",
        "gbk",
        "gb2312",
        "gb18030",
        "latin-1",
        "cp1252",
    )

    @classmethod
    def decode_bytes(cls, data: bytes) -> str:
        """使用与 read_text_file 相同的回退链解码原始字节。

        供聊天附件提取器使用，使基于路径和基于字节的调用方共享同一编码支持来源。
        """
        for encoding in cls.TEXT_DECODING_CANDIDATES:
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    @classmethod
    async def read_text_file(cls, file_path: str) -> str:
        """读取文本文件，自动检测编码。"""
        for encoding in cls.TEXT_DECODING_CANDIDATES:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue

        with open(file_path, "rb") as f:
            return f.read().decode("utf-8", errors="replace")

    @classmethod
    def needs_parser(cls, file_path: str) -> bool:
        """快速检查单个文件是否需要解析器处理。"""
        doc_type = cls.get_document_type(file_path)
        return doc_type in (
            DocumentType.PDF,
            DocumentType.DOCX,
            DocumentType.SPREADSHEET,
            DocumentType.PRESENTATION,
            DocumentType.IMAGE,
        )

    @classmethod
    def is_text_readable(cls, file_path: str) -> bool:
        """检查文件是否可以直接作为文本读取。"""
        doc_type = cls.get_document_type(file_path)
        return doc_type in (DocumentType.TEXT, DocumentType.MARKDOWN)

    @classmethod
    def get_supported_extensions(cls) -> set[str]:
        """获取所有支持的文件扩展名集合。"""
        return cls.PARSER_EXTENSIONS | cls.TEXT_EXTENSIONS | cls.IMAGE_EXTENSIONS

    @classmethod
    def has_supported_extension(cls, file_path: str | Path) -> bool:
        """当 ``file_path`` 具有支持的扩展名时返回 True。

        检查不区分大小写，因此 ``Report.PDF`` 等文件在上传、CLI、文件夹同步和重新索引中
        都能被一致发现。
        """
        return Path(file_path).suffix.lower() in cls.get_supported_extensions()

    @classmethod
    def collect_supported_files(cls, directory: str | Path, recursive: bool = False) -> list[Path]:
        """从目录中收集支持的文件，使用不区分大小写的后缀匹配。"""
        root = Path(directory)
        if not root.exists() or not root.is_dir():
            return []

        paths = root.rglob("*") if recursive else root.iterdir()
        return sorted(
            (path for path in paths if path.is_file() and cls.has_supported_extension(path)),
            key=lambda path: str(path).lower(),
        )

    @classmethod
    def get_glob_patterns(cls) -> list[str]:
        """获取文件搜索的 glob 模式。"""
        return [f"*{ext}" for ext in sorted(cls.get_supported_extensions())]
