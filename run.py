import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",   # "모듈경로:FastAPI앱인스턴스"
        host="127.0.0.1",
        port=8000,
        reload=True       # 개발 중 자동 재시작
    )
