"""Story-Export als Markdown-Bundle, EPUB oder PDF."""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from bot.story.db import StoryDB


class StoryExportError(Exception):
    pass


def _manuscript_markdown(db: StoryDB) -> str:
    meta = db.get_meta()
    title = meta.get("title", db.team_id)
    parts = [f"# {title}\n"]
    if meta:
        parts.append(
            f"*Genre:* {meta.get('genre', '')} · *Setting:* {meta.get('setting', '')}\n\n"
        )
    for ch in db.list_chapters():
        parts.append(f"\n## {ch}\n")
        for scene in db.list_scenes(ch):
            _, body = db.get_scene(ch, scene.scene_id)
            parts.append(f"\n### {scene.title}\n\n{body}\n")
    return "".join(parts)


def export_markdown_zip(db: StoryDB, out_path: Path) -> Path:
    md = _manuscript_markdown(db)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manuscript.md", md)
        meta = db.get_meta()
        if meta:
            import json

            zf.writestr("meta.json", json.dumps(meta, indent=2, ensure_ascii=False))
    return out_path


def export_epub(db: StoryDB, out_path: Path) -> Path:
    try:
        from ebooklib import epub
    except ImportError as exc:
        raise StoryExportError(
            "ebooklib fehlt — pip install ebooklib"
        ) from exc

    meta = db.get_meta()
    title = str(meta.get("title", "Story"))
    book = epub.EpubBook()
    book.set_identifier(f"story-{db.team_id}")
    book.set_title(title)
    book.set_language("de")
    chapters: list = []
    spine = ["nav"]
    toc: list = []

    for ch_id in db.list_chapters():
        ch = epub.EpubHtml(
            title=ch_id,
            file_name=f"{ch_id}.xhtml",
            lang="de",
        )
        body_parts = [f"<h1>{ch_id}</h1>"]
        for scene in db.list_scenes(ch_id):
            _, text = db.get_scene(ch_id, scene.scene_id)
            safe_title = scene.title.replace("<", "&lt;")
            body_parts.append(f"<h2>{safe_title}</h2>")
            for para in text.split("\n\n"):
                p = para.strip().replace("<", "&lt;").replace("\n", "<br/>")
                if p:
                    body_parts.append(f"<p>{p}</p>")
        ch.content = "\n".join(body_parts)
        book.add_item(ch)
        chapters.append(ch)
        spine.append(ch)
        toc.append(ch)

    book.toc = tuple(toc)
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(out_path), book)
    return out_path


def export_pdf(db: StoryDB, out_path: Path) -> Path:
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise StoryExportError("fpdf2 fehlt — pip install fpdf2") from exc

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    meta = db.get_meta()
    pdf.set_font("Helvetica", "B", 16)
    title = str(meta.get("title", "Story")).encode("latin-1", errors="replace").decode("latin-1")
    w = pdf.epw
    pdf.multi_cell(w, 10, title)
    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)
    for ch_id in db.list_chapters():
        pdf.set_font("Helvetica", "B", 14)
        pdf.multi_cell(w, 8, ch_id.encode("latin-1", errors="replace").decode("latin-1"))
        pdf.ln(2)
        pdf.set_font("Helvetica", size=11)
        for scene in db.list_scenes(ch_id):
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(
                w,
                7,
                scene.title.encode("latin-1", errors="replace").decode("latin-1"),
            )
            pdf.set_font("Helvetica", size=11)
            _, body = db.get_scene(ch_id, scene.scene_id)
            for line in body.splitlines():
                line = line.strip().encode("latin-1", errors="replace").decode("latin-1")
                if line:
                    pdf.multi_cell(w, 5, line[:200])
            pdf.ln(3)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path


def export_story(
    root: Path | str,
    team_id: str,
    fmt: str,
    *,
    out_dir: Path | None = None,
) -> Path:
    db = StoryDB(root, team_id)
    if not db.get_meta():
        raise StoryExportError("Keine Story — zuerst Story anlegen")
    base = out_dir or (Path(root) / "data" / team_id / "exports")
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    if fmt == "mdzip":
        return export_markdown_zip(db, base / f"story-{stamp}.zip")
    if fmt == "epub":
        return export_epub(db, base / f"story-{stamp}.epub")
    if fmt == "pdf":
        return export_pdf(db, base / f"story-{stamp}.pdf")
    raise StoryExportError(f"Unbekanntes Format: {fmt}")
