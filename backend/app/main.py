from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
from app.api import auth, profit_sheet, approval, dashboard, todo, master

# 테이블 생성 (Alembic 없이 개발 모드에서 사용)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LOTOS AI Profit Approval System",
    description="포워딩 영업 손익 관리 및 AI 결재 플랫폼",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth.router, prefix="/api")
app.include_router(profit_sheet.router, prefix="/api")
app.include_router(approval.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(todo.router, prefix="/api")
app.include_router(master.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/ocr")
def health_ocr():
    """OCR 환경 진단 엔드포인트"""
    import shutil, os, glob
    result: dict = {}

    result["tesseract_bin"] = shutil.which("tesseract")
    result["pdftoppm_bin"] = shutil.which("pdftoppm")
    result["TESSDATA_PREFIX_env"] = os.environ.get("TESSDATA_PREFIX", "")

    # 시스템 tessdata 경로 탐색
    candidates = [
        "/app/tessdata",
        "/usr/share/tesseract-ocr/4/tessdata",
        "/usr/share/tesseract-ocr/5/tessdata",
        "/usr/share/tessdata",
        "/usr/local/share/tessdata",
    ]
    found_tessdata: dict = {}
    for c in candidates:
        if os.path.isdir(c):
            files = [f for f in os.listdir(c) if f.endswith(".traineddata")]
            found_tessdata[c] = sorted(files)
    result["tessdata_found"] = found_tessdata

    # PyMuPDF
    try:
        import fitz
        result["pymupdf_version"] = fitz.version[0]
    except ImportError:
        result["pymupdf_version"] = None

    # 실제 OCR 가능 여부 간단 테스트
    try:
        import pytesseract
        langs = pytesseract.get_languages(config="")
        result["tesseract_langs"] = langs
    except Exception as e:
        result["tesseract_langs_error"] = str(e)

    return result


@app.get("/")
def root():
    return {"message": "LOTOS AI Profit Approval System API", "version": "1.0.0"}
