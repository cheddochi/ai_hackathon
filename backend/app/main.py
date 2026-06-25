from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.core.database import Base, engine
from app.api import auth, profit_sheet, approval, dashboard, todo, master

# 테이블 생성 (Alembic 없이 개발 모드에서 사용)
Base.metadata.create_all(bind=engine)


def _migrate_add_columns() -> None:
    """
    기존 테이블에 새 컬럼을 안전하게 추가합니다.
    PostgreSQL의 'ADD COLUMN IF NOT EXISTS'를 사용하므로 중복 실행 무해합니다.
    Alembic 없이 스키마 변경이 필요할 때 여기에 추가합니다.
    """
    statements = [
        # v1.3.0 — 인간 결재 + 환율 메모
        "ALTER TABLE profit_sheet_header ADD COLUMN IF NOT EXISTS human_decision    VARCHAR(20)",
        "ALTER TABLE profit_sheet_header ADD COLUMN IF NOT EXISTS human_comment     TEXT",
        "ALTER TABLE profit_sheet_header ADD COLUMN IF NOT EXISTS human_decided_by  VARCHAR(100)",
        "ALTER TABLE profit_sheet_header ADD COLUMN IF NOT EXISTS human_decided_at  TIMESTAMPTZ",
        "ALTER TABLE profit_sheet_header ADD COLUMN IF NOT EXISTS exchange_rate_note VARCHAR(200)",
    ]
    with engine.connect() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.commit()


_migrate_add_columns()

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
