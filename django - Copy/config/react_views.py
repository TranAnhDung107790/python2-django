"""Phục vụ bản build React (Create React App) qua cùng cổng với Django."""

from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpResponse


def react_spa(request, path=""):
    build_dir = Path(settings.BASE_DIR) / "static" / "frontend"
    index = build_dir / "index.html"
    if not index.is_file():
        return HttpResponse(
            "<!doctype html><html><head><meta charset='utf-8'><title>Chưa build React</title></head>"
            "<body style='font-family:sans-serif;padding:2rem;max-width:560px'>"
            "<h1>Chưa có bản build React</h1>"
            "<p>Trong thư mục <code>adsneaker/client</code> chạy:</p>"
            "<pre style='background:#f4f4f5;padding:12px;border-radius:8px'>npm install\nnpm run build:django</pre>"
            "<p>Sau đó tải lại <a href='/app/'>/app/</a>.</p>"
            "<p>Giao diện Django (bài thi): <a href='/'>trang chủ</a></p>"
            "</body></html>",
            status=503,
            content_type="text/html; charset=utf-8",
        )
    return FileResponse(index.open("rb"), content_type="text/html; charset=utf-8")
