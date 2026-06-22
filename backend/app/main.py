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

    # tesseract 바이너리
    result["tesseract_bin"] = shutil.which("tesseract")
    # pdftoppm (poppler)
    result["pdftoppm_bin"] = shutil.which("pdftoppm")
    # TESSDATA_PREFIX
    result["TESSDATA_PREFIX"] = os.environ.get("TESSDATA_PREFIX", "")
    # /app/tessdata 내용
    td = "/app/tessdata"
    result["app_tessdata_exists"] = os.path.isdir(td)
    if os.path.isdir(td):
        result["app_tessdata_files"] = os.listdir(td)
    # Nix store tessdata
    nix_paths = glob.glob("/nix/store/*/share/tessdata/eng.traineddata")
    result["nix_tessdata_path"] = os.path.dirname(nix_paths[0]) if nix_paths else None
    # PyMuPDF
    try:
        import fitz
        result["pymupdf_version"] = fitz.version
    except ImportError:
        result["pymupdf_version"] = None

    return result


@app.get("/")
def root():
    return {"message": "LOTOS AI Profit Approval System API", "version": "1.0.0"}
