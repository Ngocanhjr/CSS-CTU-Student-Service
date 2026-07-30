import os

import httpx
from dotenv import find_dotenv, load_dotenv


env_path = find_dotenv()
load_dotenv(env_path)

api_key = os.getenv("JINA_API_KEY", "").strip()

print("File .env:", env_path)
print("Đã đọc API key:", bool(api_key))
print("Độ dài API key:", len(api_key))

if not api_key:
    raise RuntimeError("Không đọc được JINA_API_KEY.")

payload = {
    "model": "jina-reranker-v3",
    "query": "Điều kiện đăng ký học phần là gì?",
    "documents": [
        "Sinh viên cần hoàn thành học phí trước khi đăng ký học phần.",
        "Thư viện mở cửa từ thứ Hai đến thứ Bảy.",
    ],
    "top_n": 2,
    "return_documents": False,
}

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

try:
    with httpx.Client(
        timeout=30,
        trust_env=False,
        http2=False,
        follow_redirects=True,
    ) as client:
        response = client.post(
            "https://api.jina.ai/v1/rerank",
            headers=headers,
            json=payload,
        )

        print("HTTP status:", response.status_code)
        print("Response:", response.text)

except Exception as exc:
    print("Loại lỗi:", type(exc).__name__)
    print("Chi tiết:", exc)