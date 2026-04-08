import json
import os
from urllib import request as urllib_request


def ask_chatbot(question: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "Xin chào! Hiện chatbot chưa được cấu hình GEMINI_API_KEY."
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={api_key}"
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Bạn là trợ lý bán giày AD Sneaker. Trả lời ngắn gọn, thân thiện, bằng tiếng Việt.\n"
                            f"Câu hỏi: {question}"
                        )
                    }
                ]
            }
        ]
    }
    try:
        req = urllib_request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=25) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return (
            result.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "Xin lỗi, chatbot chưa trả lời được.")
        )
    except Exception:
        return "Xin lỗi, chatbot đang bận. Bạn thử lại sau nhé."
