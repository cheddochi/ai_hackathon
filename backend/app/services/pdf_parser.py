"""
PDF Profit Sheet 파서 (rule-based, LLM 없음)
1. pdfplumber로 텍스트 추출 시도
2. 텍스트 없으면 pdf2image + pytesseract OCR fallback
3. PROFIT/LOSS SHEET 규격 rule-based 파싱
   - H.B/L NO 를 식별자로 사용
   - REVENUE OF HOUSE B/L / EXPENSE OF MASTER B/L 섹션 추출
"""
import os
import re
import glob
import json
import logging
import shutil
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import pdfplumber

logger = logging.getLogger(__name__)


# ─── 파싱 결과 데이터 클래스 ──────────────────────────────────

@dataclass
class ParsedCharge:
    charge_code: str
    charge_name: str
    is_revenue: bool       # True=매출(REVENUE), False=매입(EXPENSE)
    currency: str          # JPY / USD / KRW
    amount: float          # 외화 금액 (JPY인 경우 0)
    amount_jpy: float      # JPY 환산 금액
    ex_rate: float = 0.0
    account_name: str = "" # ACCOUNT CUST 명
    confidence: float = 1.0


@dataclass
class ParsedProfitSheet:
    # 식별자
    hbl_no: str = ""       # H.B/L NO (House B/L Number) - 계약 식별자
    mbl_no: str = ""       # M.B/L NO (Master B/L)
    ref_no: str = ""       # REF NO
    # 선적 정보
    vessel_voy: str = ""
    etd: str = ""
    eta: str = ""
    pol: str = ""          # Port of Loading
    pod: str = ""          # Port of Discharge
    weight_kg: Optional[float] = None
    cbm: Optional[float] = None
    r_ton: Optional[float] = None
    cntr_info: str = ""    # Container Info
    partner: str = ""      # 지불처 / PARTNER
    # 거래처
    customer_name: str = ""
    assignee_name: str = ""
    # 환율
    ex_rate_usd: float = 0.0
    # Profit/Loss 합계
    profit_usd: float = 0.0
    profit_jpy: float = 0.0
    profit_tot_jpy: float = 0.0
    # 비용 항목
    charges: List[ParsedCharge] = field(default_factory=list)
    # 메타
    raw_text: str = ""
    is_ocr: bool = False
    parse_warnings: List[str] = field(default_factory=list)
    confidence: float = 1.0

    # ── 하위 호환 프로퍼티 ──
    @property
    def case_no(self) -> str:
        return self.hbl_no or self.ref_no

    @property
    def origin_port(self) -> str:
        return self.pol

    @property
    def dest_port(self) -> str:
        return self.pod

    @property
    def job_code(self) -> str:
        return _infer_job_code(self.pol, self.pod)

    @property
    def container_type(self) -> str:
        return self.cntr_info

    @property
    def base_currency(self) -> str:
        return "JPY"

    @property
    def partner_name(self) -> str:
        return self.partner


# ─── 유틸 ────────────────────────────────────────────────────

def _parse_float(s: str) -> float:
    try:
        return float(re.sub(r'[,\s]', '', str(s)))
    except (ValueError, AttributeError):
        return 0.0


def _infer_job_code(pol: str, pod: str) -> str:
    """POL/POD에서 업무코드 추론"""
    pol_u = (pol or "").upper()
    pod_u = (pod or "").upper()
    kr_ports = ["BUSAN", "INCHEON", "KOREA"]
    jp_ports = ["TOKYO", "OSAKA", "NAGOYA", "YOKOHAMA", "KOBE", "FUKUOKA", "JAPAN"]
    pol_kr = any(p in pol_u for p in kr_ports)
    pol_jp = any(p in pol_u for p in jp_ports)
    pod_kr = any(p in pod_u for p in kr_ports)
    pod_jp = any(p in pod_u for p in jp_ports)

    if pol_kr and pod_jp:
        return "SI"   # 한국 → 일본 수입
    if pol_jp and pod_kr:
        return "SE"   # 일본 → 한국 수출
    if pol_jp:
        return "AE"   # 일본에서 수출
    return "SE"


# ─── 텍스트 추출 ─────────────────────────────────────────────

def _extract_text_pdfplumber(file_path: str) -> str:
    texts: List[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                texts.append(t)
    return "\n\n".join(texts)


def _setup_ocr_env() -> tuple:
    """
    Railway(Nix) 환경에서 poppler / tesseract 경로를 동적으로 탐지한다.
    Returns: (poppler_path | None, available_langs: list[str])
    """
    # ── 1. poppler (pdftoppm) 경로 탐지 ──────────────────────────
    pdftoppm = shutil.which("pdftoppm")
    poppler_path = os.path.dirname(pdftoppm) if pdftoppm else None
    logger.info(f"[OCR-setup] pdftoppm={pdftoppm}, poppler_path={poppler_path}")

    # ── 2. tesseract 바이너리 경로 탐지 ──────────────────────────
    try:
        import pytesseract
        tess_bin = shutil.which("tesseract")
        if tess_bin:
            pytesseract.pytesseract.tesseract_cmd = tess_bin
            logger.info(f"[OCR-setup] tesseract_cmd={tess_bin}")
    except ImportError:
        pass

    # ── 3. TESSDATA_PREFIX 자동 설정 ──────────────────────────────
    tessdata_prefix = os.environ.get("TESSDATA_PREFIX", "")
    if not tessdata_prefix or not os.path.isdir(tessdata_prefix):
        # 우선순위별 탐색
        candidates = [
            "/app/tessdata",                           # nixpacks 빌드 다운로드
            "/tessdata",
            "/usr/share/tesseract-ocr/4/tessdata",    # Debian/Ubuntu apt
            "/usr/share/tesseract-ocr/5/tessdata",    # Debian/Ubuntu apt (v5)
            "/usr/share/tessdata",                     # Ubuntu 공통
            "/usr/local/share/tessdata",
        ]
        for candidate in candidates:
            if os.path.isfile(os.path.join(candidate, "eng.traineddata")):
                tessdata_prefix = candidate
                break

        if not tessdata_prefix:
            nix_paths = glob.glob("/nix/store/*/share/tessdata/eng.traineddata")
            if nix_paths:
                tessdata_prefix = os.path.dirname(nix_paths[0])

        if tessdata_prefix:
            os.environ["TESSDATA_PREFIX"] = tessdata_prefix
            logger.info(f"[OCR-setup] TESSDATA_PREFIX={tessdata_prefix}")

    # ── 4. 사용 가능한 언어 확인 ─────────────────────────────────
    available_langs: list = []
    if tessdata_prefix and os.path.isdir(tessdata_prefix):
        for lang in ("jpn", "kor", "eng"):
            td = os.path.join(tessdata_prefix, f"{lang}.traineddata")
            if os.path.isfile(td):
                available_langs.append(lang)
    logger.info(f"[OCR-setup] available_langs={available_langs}")

    return poppler_path, available_langs


MAX_OCR_PAGES = 3   # P&L 데이터는 1~3페이지에 집중
OCR_DPI       = 150  # 메모리 절약 (200DPI 대비 ~44% 감소)


def _pdf_to_images(file_path: str) -> list:
    """
    PDF → PIL Image 리스트 변환 (최대 MAX_OCR_PAGES 페이지)
    우선순위: PyMuPDF (외부 바이너리 불필요) → pdf2image (poppler 필요)
    """
    # ── 방법 1: PyMuPDF (fitz) ─────────────────────────────────
    try:
        import fitz  # PyMuPDF
        from PIL import Image
        import io

        doc = fitz.open(file_path)
        total = len(doc)
        target = min(total, MAX_OCR_PAGES)
        images = []
        scale = OCR_DPI / 72
        mat = fitz.Matrix(scale, scale)

        for page_no in range(target):
            page = doc[page_no]
            # colorspace=fitz.csGRAY → 메모리 절약
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes)).convert("L")  # 그레이스케일
            images.append(img)
            pix = None  # 즉시 해제

        doc.close()
        logger.info(f"[OCR] PyMuPDF: {len(images)}/{total} 페이지 변환 완료 ({OCR_DPI}dpi)")
        return images

    except ImportError:
        logger.info("[OCR] PyMuPDF 없음 → pdf2image 시도")
    except Exception as e:
        logger.warning(f"[OCR] PyMuPDF 실패: {e} → pdf2image 시도")

    # ── 방법 2: pdf2image (poppler 필요) ──────────────────────
    try:
        from pdf2image import convert_from_path

        poppler_path, _ = _setup_ocr_env()
        pages = convert_from_path(
            file_path, dpi=OCR_DPI,
            poppler_path=poppler_path,
            last_page=MAX_OCR_PAGES,
            grayscale=True,
        )
        logger.info(f"[OCR] pdf2image: {len(pages)} 페이지 변환 완료")
        return pages
    except Exception as e:
        logger.error(f"[OCR] pdf2image 실패: {e}")

    return []


def _extract_text_ocr(file_path: str) -> str:
    """OCR fallback: PyMuPDF/pdf2image → pytesseract"""
    try:
        import pytesseract

        _, available_langs = _setup_ocr_env()

        pages = _pdf_to_images(file_path)
        if not pages:
            logger.error(f"[OCR] PDF→이미지 변환 실패: {file_path}")
            return ""

        # 언어 후보 (설치된 tessdata 기준)
        if "jpn" in available_langs and "kor" in available_langs:
            lang_candidates = ["jpn+kor+eng", "jpn+eng", "eng"]
        elif "jpn" in available_langs:
            lang_candidates = ["jpn+eng", "eng"]
        elif available_langs:
            lang_candidates = ["+".join(available_langs), "eng"]
        else:
            lang_candidates = ["jpn+kor+eng", "jpn+eng", "eng"]

        texts: List[str] = []
        for page_img in pages:
            for lang in lang_candidates:
                try:
                    text = pytesseract.image_to_string(
                        page_img,
                        lang=lang,
                        config="--psm 6 --oem 3",
                    )
                    if text.strip():
                        texts.append(text)
                        break
                except Exception as e:
                    logger.debug(f"[OCR] lang={lang} 실패: {e}")
                    continue

        result_text = "\n\n".join(texts)
        logger.info(f"[OCR] 완료: {len(result_text)} chars, langs={lang_candidates}")
        return result_text

    except Exception as e:
        logger.error(f"[pdf_parser] OCR 전체 실패: {e}", exc_info=True)
        return ""


# ─── 헤더 파싱 ───────────────────────────────────────────────

def _extract_header(text: str) -> dict:
    result: dict = {}

    def _find(pattern: str, group: int = 1) -> str:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return m.group(group).strip() if m else ""

    result['ref_no']       = _find(r'REF\s*NO\s*\.?\s*:\s*([A-Z0-9\-]{4,30})')
    result['mbl_no']       = _find(r'M\s*\.?\s*B/?L\s*NO\s*\.?\s*:\s*([A-Z0-9\-]{4,30})')
    result['vessel_voy']   = _find(r'VESSEL\s*/\s*VOY\s*:\s*(.+?)(?:\s{3,}|\n|$)')
    result['assignee_name']= _find(r'(?:出力担当者|担当者)\s*:\s*([A-Z][A-Z\.\s]+?)(?:\s+PRINT|\n|$)')

    # ETD / ETA
    m = re.search(r'ETD\s*/\s*ETA\s*:\s*([\d\-/]+)\s*/\s*([\d\-/]+)', text, re.IGNORECASE)
    result['etd'] = m.group(1).strip() if m else ""
    result['eta'] = m.group(2).strip() if m else ""

    # POL / POD  (일본어 앞에 영어 항구명이 오는 형식)
    result['pol'] = _find(r'POL\s*:\s*([A-Z][A-Z,\.\s]+?)(?:\s{3,}|\n|$)')
    result['pod'] = _find(r'POD\s*:\s*([A-Z][A-Z,\.\s]+?)(?:\s{3,}|\n|$)')

    # WEIGHT / CBM
    m = re.search(r'WEIGHT\s*:\s*([\d,\.]+)\s*KGS?', text, re.IGNORECASE)
    result['weight_kg'] = _parse_float(m.group(1)) if m else None

    m = re.search(r'CBM\s*:\s*([\d,\.]+)\s*CBM', text, re.IGNORECASE)
    result['cbm'] = _parse_float(m.group(1)) if m else None

    result['cntr_info'] = _find(r'CNTR\s*INFO\s*:\s*(.+?)(?:\s{3,}|\n|$)')

    # PARTNER (지불처) - 두 가지 표기
    partner = _find(r'PARTNER\s*:\s*(.+?)(?:\s{3,}|\n|$)')
    if not partner:
        partner = _find(r'支払先\s*:\s*(.+?)(?:\s{3,}|\n|$)')
    result['partner'] = partner

    # SHIPPER (Commercial Invoice 기반)
    result['shipper'] = _find(r'SHIPPER\s*:\s*([A-Z][A-Z0-9\s\.\,]+?)(?:\n|$)')

    # CONSIGNEE / 수입자 — "For Account of Risk of Messrs." 다음 줄 또는 직접 패턴
    cns = _find(r'For\s+Account\s+of\s+Risk\s+of\s+Messrs\.\s*\n(.+?)(?:\n|$)')
    if not cns:
        cns = _find(r'CONSIGNEE\s*:\s*([A-Z][A-Z0-9\s\.\,]+?)(?:\n|$)')
    result['consignee'] = cns

    # 품목 (Description of Goods — Packing List / Commercial Invoice)
    goods = _find(r'(?:POLYAMIDE|NYLON|CHIP|CARGO|GOODS|COMMODITY)\s*[:\-]?\s*(.{5,80})(?:\n|$)')
    if not goods:
        goods = _find(r'(?:1\))\s*([A-Z][A-Z0-9\s\(\)]+?)(?:\n|$)')
    result['goods'] = goods

    # 보험 가입액 (Sum Insured)
    m_ins = re.search(r'[¥￥]\s*([\d,]+)\s*[\.\-]', text)
    if m_ins:
        result['sum_insured'] = _parse_float(m_ins.group(1))
    else:
        result['sum_insured'] = None

    return result


# ─── H.B/L NO + R/TON + Customer 추출 ──────────────────────

def _extract_hbl_info(text: str) -> Tuple[str, str, float]:
    """H.B/L NO, customer_name, R/TON 추출"""
    hbl_no = ""
    customer_name = ""
    r_ton = 0.0

    # 방법 1: summary 테이블 데이터 행 — HBL이 R/TON 앞에 있음
    # 패턴: "HBLCODE  R/TON_VALUE |USD|"
    m = re.search(
        r'^([A-Z0-9]{6,20})\s+([\d,\.]+)\s*[|]?USD',
        text,
        re.MULTILINE,
    )
    if m:
        hbl_no = m.group(1).strip()
        r_ton  = _parse_float(m.group(2))
    else:
        # 방법 2: H.B/L NO 레이블 뒤
        m = re.search(r'H\.?\s*B/?L\s*NO[.\s]*:?\s*([A-Z0-9]{6,20})', text, re.IGNORECASE)
        if m:
            hbl_no = m.group(1).strip()

    # Customer name: HBL 이후 3번째 줄 내에서 숫자/기호 아닌 텍스트
    if hbl_no:
        idx = text.find(hbl_no)
        if idx >= 0:
            after_lines = text[idx:idx + 400].split('\n')
            for line in after_lines[1:5]:
                line = line.strip()
                if not line:
                    continue
                # 날짜, 숫자, 통화코드만 있는 줄 스킵
                if re.match(r'^[\d\-/|JPYUSD\s,\.\[\]]+$', line):
                    continue
                # 섹션 헤더 스킵
                if any(kw in line.upper() for kw in
                       ['TOTAL', 'REVENUE', 'EXPENSE', 'PROFIT', 'PARTNER', 'ACCOUNT']):
                    continue
                if len(line) > 2:
                    customer_name = line
                    break

    return hbl_no, customer_name, r_ton


# ─── 환율 추출 ───────────────────────────────────────────────

def _extract_ex_rate(text: str) -> float:
    """USD/JPY 환율 추출"""
    # "USD 160.5600" or "USD 160.5600JPY" 패턴
    m = re.search(r'USD\s+(1[0-9]{2}\.[0-9]{2,4})', text)
    if m:
        return _parse_float(m.group(1))
    return 0.0


# ─── 비용 항목 추출 ──────────────────────────────────────────

def _parse_charge_line(line: str) -> Optional[ParsedCharge]:
    """
    단일 비용 항목 줄 파싱
    형식 A (코드 분리):  CODE  DESCRIPTION  CURRENCY  EXRATE  amounts...
    형식 B (코드 없음):  DESCRIPTION(긴 이름)  CURRENCY  EXRATE  amounts...
    예시:
      BF BAF USD 160.5600 310.00 49,774 310.00 49,774
      TH THC JPY 160.5600 52,000 52,000
      CC CUSTOMS CLEARANCE FEE JPY 160.5600 11,800 11,800
      INSURANCE FEE(B/L) JPY 160.8400 48,000 48,000   ← 보험 서류
    """
    line = line.strip()
    if not line:
        return None

    # 패턴 A: 2~5글자 CODE + 설명 + 통화 + 환율 + 금액
    m = re.match(
        r'^([A-Z]{2,5})\s+(.+?)\s+(JPY|USD|KRW)\s+([\d,\.]+)\s+([\d\.,\s\|\-]+)$',
        line,
    )
    if m:
        code     = m.group(1).upper()
        name     = m.group(2).strip()
        currency = m.group(3).upper()
        ex_rate  = _parse_float(m.group(4))
        nums_str = m.group(5)
    else:
        # 패턴 B: CODE 없이 긴 설명명이 바로 시작 (INSURANCE FEE 등)
        m2 = re.match(
            r'^(.+?)\s+(JPY|USD|KRW)\s+([\d,\.]+)\s+([\d\.,\s\|\-]+)$',
            line,
        )
        if not m2:
            return None
        raw_name = m2.group(1).strip()
        # 설명이 너무 짧거나 숫자/특수문자만이면 스킵
        if len(raw_name) < 3 or re.match(r'^[\d\s,\.\-\|]+$', raw_name):
            return None
        # 코드 자동 생성: 첫 단어 앞 3글자 대문자
        code     = re.sub(r'[^A-Z]', '', raw_name.upper())[:5] or "MISC"
        name     = raw_name
        currency = m2.group(2).upper()
        ex_rate  = _parse_float(m2.group(3))
        nums_str = m2.group(4)

    # 숫자 추출 (콤마 제거 후)
    raw_nums = re.findall(r'-?[\d]+(?:,[\d]{3})*(?:\.[\d]+)?', nums_str)
    nums = [_parse_float(n) for n in raw_nums if n.replace(',', '').replace('.', '').replace('-', '')]
    nums = [n for n in nums if n != 0.0]

    if not nums:
        return None

    if currency == 'JPY':
        amount_jpy = nums[-1]
        amount     = 0.0
    else:  # USD / KRW
        small = [n for n in nums if abs(n) < 10_000]
        large = [n for n in nums if abs(n) >= 1_000]
        amount     = small[-1] if small else nums[0]
        amount_jpy = large[-1] if large else (abs(amount) * ex_rate if ex_rate else 0.0)

    return ParsedCharge(
        charge_code  = code,
        charge_name  = name,
        is_revenue   = True,   # caller가 덮어씀
        currency     = currency,
        amount       = amount,
        amount_jpy   = amount_jpy,
        ex_rate      = ex_rate,
        confidence   = 0.9,
    )


def _extract_charges(text: str) -> List[ParsedCharge]:
    """REVENUE / EXPENSE 섹션에서 전체 비용 항목 추출"""
    charges: List[ParsedCharge] = []

    # 섹션 경계 찾기
    rev_m = re.search(
        r'REVENUE\s+OF\s+HOUSE\s+B/L(.+?)(?=EXPENSE\s+OF\s+MASTER|PARTNER\s+CLEARANCE|'
        r'PROFIT\s+USD|\Z)',
        text,
        re.DOTALL | re.IGNORECASE,
    )
    exp_m = re.search(
        r'EXPENSE\s+OF\s+MASTER\s+B/L(.+?)(?=PARTNER\s+CLEARANCE|PROFIT\s+USD|\Z)',
        text,
        re.DOTALL | re.IGNORECASE,
    )

    if rev_m:
        charges.extend(_parse_section(rev_m.group(1), is_revenue=True))
    if exp_m:
        charges.extend(_parse_section(exp_m.group(1), is_revenue=False))

    return charges


def _parse_section(section: str, is_revenue: bool) -> List[ParsedCharge]:
    """섹션 텍스트에서 비용 항목 파싱"""
    charges: List[ParsedCharge] = []
    current_account = ""

    for line in section.split('\n'):
        line_s = line.strip()
        if not line_s:
            continue

        # ACCOUNT CUST
        m = re.match(r'ACCOUNT\s+CUST\s*:\s*(.+)', line_s, re.IGNORECASE)
        if m:
            current_account = m.group(1).strip()
            continue

        # SUB TOTAL / TOTAL 스킵
        if re.match(r'^(SUB\s+)?TOTAL\b', line_s, re.IGNORECASE):
            continue
        if re.match(r'^ITEM\b', line_s, re.IGNORECASE):
            continue

        parsed = _parse_charge_line(line_s)
        if parsed:
            parsed.is_revenue  = is_revenue
            parsed.account_name = current_account
            charges.append(parsed)

    return charges


# ─── Profit 합계 추출 ────────────────────────────────────────

def _extract_profit(text: str) -> Tuple[float, float, float]:
    profit_usd    = 0.0
    profit_jpy    = 0.0
    profit_tot_jpy = 0.0

    m = re.search(r'PROFIT\s+USD\s+([-\d,\.]+)', text, re.IGNORECASE)
    if m:
        profit_usd = _parse_float(m.group(1))

    # "PROFIT USD xxx\nJPY yyy" or "JPY yyy" after PROFIT line
    m = re.search(
        r'PROFIT\s+USD\s+[-\d,\.]+\s*\n\s*(?:JPY\s+)?([-\d,\.]+)',
        text,
        re.IGNORECASE,
    )
    if m:
        profit_jpy = _parse_float(m.group(1))

    m = re.search(r'TOT\(J\)\s+([-\d,\.]+)', text, re.IGNORECASE)
    if m:
        profit_tot_jpy = _parse_float(m.group(1))

    return profit_usd, profit_jpy, profit_tot_jpy


# ─── 메인 함수 ───────────────────────────────────────────────

def parse_pdf(file_path: str) -> ParsedProfitSheet:
    """
    PDF 파싱 메인 엔트리포인트
    1. pdfplumber 시도
    2. 텍스트 없으면 OCR fallback
    3. PROFIT/LOSS SHEET rule-based 파싱
    """
    result = ParsedProfitSheet()
    is_ocr = False

    try:
        # ── Step 1: pdfplumber ──────────────────────────────
        text = _extract_text_pdfplumber(file_path)

        # ── Step 2: OCR fallback ─────────────────────────────
        if not text or len(text.strip()) < 100:
            logger.info(f"[pdf_parser] Falling back to OCR: {file_path}")
            text = _extract_text_ocr(file_path)
            is_ocr = True

        if not text or len(text.strip()) < 50:
            result.parse_warnings.append("텍스트 추출 실패 (pdfplumber + OCR 모두 실패)")
            result.confidence = 0.0
            return result

        result.raw_text = text
        result.is_ocr   = is_ocr

        # ── Step 3: PROFIT/LOSS SHEET 형식 확인 ─────────────
        text_upper = text.upper()
        if 'PROFIT' not in text_upper:
            result.parse_warnings.append("PROFIT/LOSS SHEET 형식이 아닙니다.")
            result.confidence = 0.2
            return result

        # ── Step 4: 헤더 ─────────────────────────────────────
        hdr = _extract_header(text)
        result.ref_no        = hdr.get('ref_no', '')
        result.mbl_no        = hdr.get('mbl_no', '')
        result.vessel_voy    = hdr.get('vessel_voy', '')
        result.etd           = hdr.get('etd', '')
        result.eta           = hdr.get('eta', '')
        result.pol           = hdr.get('pol', '')
        result.pod           = hdr.get('pod', '')
        result.weight_kg     = hdr.get('weight_kg')
        result.cbm           = hdr.get('cbm')
        result.cntr_info     = hdr.get('cntr_info', '')
        result.partner       = hdr.get('partner', '')
        result.assignee_name = hdr.get('assignee_name', '')

        # ── Step 5: H.B/L NO ─────────────────────────────────
        hbl_no, customer_name, r_ton = _extract_hbl_info(text)
        result.hbl_no        = hbl_no
        result.customer_name = customer_name
        result.r_ton         = r_ton if r_ton else (
            max(result.weight_kg / 1000.0, result.cbm)
            if result.weight_kg and result.cbm else result.cbm
        )

        # ── Step 6: 환율 ─────────────────────────────────────
        result.ex_rate_usd = _extract_ex_rate(text)

        # ── Step 7: 비용 항목 ────────────────────────────────
        result.charges = _extract_charges(text)

        # ── Step 8: Profit 합계 ──────────────────────────────
        result.profit_usd, result.profit_jpy, result.profit_tot_jpy = _extract_profit(text)

        # ── 신뢰도 계산 ─────────────────────────────────────
        result.confidence = 0.7 if is_ocr else 0.9
        if not result.hbl_no:
            result.parse_warnings.append("H.B/L NO를 추출하지 못했습니다.")
            result.confidence = max(0.1, result.confidence - 0.2)
        if not result.charges:
            result.parse_warnings.append("비용 항목 추출 실패. 수동 입력이 필요합니다.")
            result.confidence = max(0.1, result.confidence - 0.2)

    except Exception as exc:
        logger.error(f"[pdf_parser] Unexpected error: {exc}", exc_info=True)
        result.parse_warnings.append(f"파싱 오류: {exc}")
        result.confidence = 0.0

    return result
