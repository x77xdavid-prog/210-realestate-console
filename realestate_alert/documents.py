"""부동산에서 받은 매물 서류 파일 보관 — 매물장 항목(identity)별 폴더에 저장.

저장 위치는 데이터베이스 파일 옆 `documents/` 폴더라서,
로컬에서는 data/documents, Render에서는 영구 디스크 /data/documents에 보존된다.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

MAX_DOCUMENT_BYTES = 15 * 1024 * 1024  # 서류 한 건당 15MB 제한

# 브라우저에서 바로 열어도 안전한 형식만 inline (SVG는 스크립트 실행 위험으로 제외)
_INLINE_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def documents_root(database_path: Path) -> Path:
    return Path(database_path).parent / "documents"


def safe_identity(identity: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]", "_", str(identity))
    if not cleaned or set(cleaned) <= {".", "_"}:
        raise ValueError(f"사용할 수 없는 매물 식별자: {identity!r}")
    return cleaned


def safe_filename(filename: str) -> str:
    """경로 조작을 차단하고 한글 등 일반 문자는 보존한 파일명을 돌려준다."""
    name = Path(str(filename).replace("\\", "/")).name.strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    if not name or name in (".", "..") or name.startswith("."):
        raise ValueError(f"사용할 수 없는 파일명: {filename!r}")
    return name


def content_disposition_for(filename: str) -> tuple[str, str]:
    ext = Path(filename).suffix.lower()
    if ext in _INLINE_CONTENT_TYPES:
        return _INLINE_CONTENT_TYPES[ext], "inline"
    return "application/octet-stream", "attachment"


def save_document(database_path: Path, identity: str, filename: str, content: bytes) -> Path:
    if not content:
        raise ValueError("빈 파일은 저장할 수 없습니다.")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise ValueError(f"파일이 {MAX_DOCUMENT_BYTES // (1024 * 1024)}MB 제한을 초과합니다.")
    folder = documents_root(database_path) / safe_identity(identity)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / safe_filename(filename)
    target.write_bytes(content)
    return target


def list_documents(database_path: Path, identity: str) -> list[dict]:
    folder = documents_root(database_path) / safe_identity(identity)
    if not folder.exists():
        return []
    return sorted(
        (
            {"name": item.name, "size": item.stat().st_size}
            for item in folder.iterdir()
            if item.is_file()
        ),
        key=lambda entry: entry["name"],
    )


def count_all_documents(database_path: Path) -> dict[str, int]:
    """매물장 배지용 — 폴더(정리된 identity)별 서류 개수."""
    root = documents_root(database_path)
    if not root.exists():
        return {}
    return {
        folder.name: sum(1 for item in folder.iterdir() if item.is_file())
        for folder in root.iterdir()
        if folder.is_dir()
    }


def document_path(database_path: Path, identity: str, filename: str) -> Path | None:
    target = documents_root(database_path) / safe_identity(identity) / safe_filename(filename)
    return target if target.is_file() else None


def delete_document(database_path: Path, identity: str, filename: str) -> bool:
    target = document_path(database_path, identity, filename)
    if target is None:
        return False
    target.unlink()
    return True


def delete_all_documents(database_path: Path, identity: str) -> None:
    folder = documents_root(database_path) / safe_identity(identity)
    if folder.exists():
        shutil.rmtree(folder)
