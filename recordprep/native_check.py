"""Native capability and synthetic embedded-PDF smoke checks; no AI or GPU work."""
from __future__ import annotations

import io


def check_native() -> dict:
    try:
        import gi
        for namespace, version in (("Gtk", "4.0"), ("Adw", "1"), ("Vte", "3.91"), ("GdkPixbuf", "2.0")):
            gi.require_version(namespace, version)
        from gi.repository import Gtk, Adw, Vte, GLib
        versions = {"glib": (GLib.MAJOR_VERSION, GLib.MINOR_VERSION, GLib.MICRO_VERSION),
                    "gtk": (Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version()),
                    "adwaita": (Adw.get_major_version(), Adw.get_minor_version(), Adw.get_micro_version())}
        required = {"glib": (2, 80, 0), "gtk": (4, 12, 0), "adwaita": (1, 4, 0)}
        apis = (hasattr(Gtk, "FileDialog")
                and all(hasattr(Adw, name) for name in
                        ("ToolbarView", "EntryRow", "ComboRow", "OverlaySplitView",
                         "Breakpoint", "BreakpointCondition", "SwitchRow", "MessageDialog"))
                and all(hasattr(Vte.Terminal, name) for name in ("spawn_async", "set_color_background")))
        import pymupdf
        import pdftotext
        from pypdf import PdfReader
        document = pymupdf.open()
        page = document.new_page(width=200, height=100)
        page.insert_text((20, 40), "Synthetic RecordPrep check")
        content = document.tobytes()
        document.close()
        text = pdftotext.PDF(io.BytesIO(content), physical=True)
        reader = PdfReader(io.BytesIO(content))
        with pymupdf.open(stream=content, filetype="pdf") as rendered:
            pixmap = rendered[0].get_pixmap(matrix=pymupdf.Matrix(300 / 72, 300 / 72), colorspace=pymupdf.csGRAY)
            pdf_ok = (len(text) == len(reader.pages) == 1 and "Synthetic RecordPrep check" in text[0]
                      and pixmap.width > 0 and pixmap.height > 0 and pixmap.n == 1)
        return {"ok": apis and pdf_ok and all(versions[k] >= v for k, v in required.items()),
                "versions": versions, "apis": apis, "pdf": pdf_ok, "vte_namespace": "3.91"}
    except (ImportError, ValueError, AttributeError, OSError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc)}


if __name__ == "__main__":
    import json
    import sys
    result = check_native()
    print(json.dumps(result))
    sys.exit(0 if result["ok"] else 1)
