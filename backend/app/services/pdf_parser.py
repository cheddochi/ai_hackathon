"""
PDF Profit Sheet 파서 (rule-based, LLM 없음)
pdfplumber를 이용해 텍스트 추출 후 정규식 기반 구조화
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import pdfplumber


# ─── 파싱 결과 데이터 클래스 ───────────────────────────────
@dataclass
class ParsedCharge:
    charge_code: str
    charge_name: str
    is_revenue: bool        # True=매출, False=매입
    currency: str
    amount: float
    partner_name: str = ""
    quantity: float = 1.0
    unit: str = ""
    confidence: float = 1.0  # 파싱 신뢰도 (0~1)


@dataclass
class ParsedProfitSheet:
    case_no: str = ""
    customer_name: str = ""
    job_code: str = ""
    assignee_name: str = ""
    origin_port: str = ""
    dest_port: str = ""
    partner_name: str = ""
    weight_kg: Optional[float] = None
    cbm: Optional[float] = None
    container_type: str = ""
    base_currency: str = "JPY"
    charges: List[ParsedCharge] = field(default_factory=list)
    raw_text: str = ""
    parse_warnings: List[str] = field(default_factory=list)


# ─── 알려진 비용 항목 코드 매핑 ──────────────────────────
KNOWN_CHARGES = {
    # 해상
    "OF": ("Ocean Freight", "SEA"),
    "THC": ("Terminal Handling Charge", "SEA"),
    "BAF": ("Bunker Adjustment Factor", "SEA"),
    "WAF": ("Fuel Surcharge", "SEA"),
    "CIC": ("Container Imbalance Charge", "SEA"),
    "EBS": ("Emergency Bunker Surcharge", "SEA"),
    "CRS": ("Container Recovery Surcharge", "SEA"),
    "EFS": ("Environmental Fuel Surcharge", "SEA"),
    # 서류
    "DOC": ("Document Fee", "ALL"),
    "BL": ("Bill of Lading Fee", "SEA"),
    "DO": ("Delivery Order Fee", "SEA"),
    "SEAL": ("Seal Charge", "SEA"),
    # 수출
    "AFR": ("Advance Filing Rules", "ALL"),
    "AMS": ("Automated Manifest System", "SEA"),
    "ENS": ("Entry Summary Declaration", "ALL"),
    "ISPS": ("Port Security Fee", "SEA"),
    # 수입
    "DUTY": ("관세", "ALL"),
    "VAT": ("소비세", "ALL"),
    "FOOD": ("식품신고", "ALL"),
    "QUARANTINE": ("검역", "ALL"),
    "INSPECTION": ("검사", "ALL"),
    # 운송
    "DRAYAGE": ("컨테이너 운송", "ALL"),
    "HIGHWAY": ("고속도로비", "ALL"),
    "DELIVERY": ("배송비", "ALL"),
    # 창고
    "STORAGE": ("보관료", "ALL"),
    "DEVAN": ("데반닝", "ALL"),
    "VANNING": ("바닝", "ALL"),
    "PICKING": ("피킹", "ALL"),
    "LABELING": ("라벨링", "ALL"),
    "HANDLING": ("작업료", "ALL"),
    # 항공
    "AF": ("Air Freight", "AIR"),
    "FSC": ("Fuel Surcharge", "AIR"),
    "SSC": ("Security Surcharge", "AIR"),
    "AWB": ("Air Waybill Fee", "AIR"),
}

CURRENCY_PATTERNS = {
    "JPY": [r"¥", r"JPY", r"円", r"¥"],
    "USD": [r"\$", r"USD"],
    "KRW": [r"KRW", r"원", r"₩"],
    "EUR": [r"EUR", r"€"],
}

AMOUNT_PATTERN = re.compile(
    r"([\$¥₩€]?\s*[\d,]+(?:\.\d{1,2})?)\s*(JPY|USD|KRW|EUR|円|¥|\$|₩|€)?",
    re.IGNORECASE,
)

JOB_CODE_PATTERN = re.compile(
    r"\b(SE\+{0,3}|SI\+{0,3}|AE\+{0,3}|AI\+{0,3}|PJT)\b",
    re.IGNORECASE,
)

REVENUE_KEYWORDS = ["売上", "REVENUE", "SALES", "CHARGE TO", "매출", "수입"]
COST_KEYWORDS = ["仕入", "COST", "PURCHASE", "PAYABLE", "매입", "원가", "支払"]


def parse_pdf(file_path: str) -> ParsedProfitSheet:
    """PDF 파일을 파싱하여 ParsedProfitSheet 반환"""
    result = ParsedProfitSheet()

    try:
        with pdfplumber.open(file_path) as pdf:
            all_text = ""
            all_tables = []

            for page in pdf.pages:
                text = page.extract_text() or ""
                all_text += text + "\n"
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)

        result.raw_text = all_text

        # 메타 정보 추출
        result.case_no = _extract_case_no(all_text)
        result.customer_name = _extract_customer(all_text)
        result.job_code = _extract_job_code(all_text)
        result.assignee_name = _extract_assignee(all_text)
        result.origin_port, result.dest_port = _extract_ports(all_text)
        result.weight_kg = _extract_weight(all_text)
        result.cbm = _extract_cbm(all_text)
        result.container_type = _extract_container_type(all_text)
        result.base_currency = _detect_base_currency(all_text)

        # 테이블에서 매출/매입 항목 추출
        if all_tables:
            charges = _parse_tables(all_tables, all_text)
            result.charges = charges
        else:
            # 테이블 없으면 텍스트 기반 파싱
            charges = _parse_text_charges(all_text)
            result.charges = charges

        if not result.charges:
            result.parse_warnings.append("비용 항목을 추출하지 못했습니다. 수동 입력이 필요합니다.")

    except Exception as e:
        result.parse_warnings.append(f"PDF 파싱 오류: {str(e)}")

    return result


def _extract_case_no(text: str) -> str:
    patterns = [
        r"(?:Case\s*No|안건번호|案件番号)[:\s#]*([\w\-/]+)",
        r"(?:B/L No|BL No)[:\s]*([\w\-/]+)",
        r"(?:JOB|Job)[:\s#]*([\w\-/]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _extract_customer(text: str) -> str:
    patterns = [
        r"(?:Customer|Shipper|荷主|거래처)[:\s]*([\w\s\-\.]+?)(?:\n|,|;)",
        r"(?:CONSIGNEE|SHIPPER)[:\s]*([\w\s\-\.]+?)(?:\n)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _extract_job_code(text: str) -> str:
    m = JOB_CODE_PATTERN.search(text)
    return m.group(1).upper() if m else ""


def _extract_assignee(text: str) -> str:
    patterns = [
        r"(?:担当者|담당자|Assignee|担当)[:\s]*([\w\s]+?)(?:\n|,)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _extract_ports(text: str) -> Tuple[str, str]:
    origin, dest = "", ""
    # PORT 패턴: "FROM TOKYO" or "ORIGIN: TOKYO"
    m_origin = re.search(r"(?:FROM|ORIGIN|POL|出発)[:\s]*([\w\s]+?)(?:\n|→|->|TO|DEST)", text, re.IGNORECASE)
    m_dest = re.search(r"(?:TO|DEST|DESTINATION|POD|到着)[:\s]*([\w\s]+?)(?:\n|,)", text, re.IGNORECASE)
    if m_origin:
        origin = m_origin.group(1).strip().upper()
    if m_dest:
        dest = m_dest.group(1).strip().upper()
    return origin, dest


def _extract_weight(text: str) -> Optional[float]:
    m = re.search(r"(?:Weight|重量|G\.W)[:\s]*([\d,\.]+)\s*(?:KG|kg|K)", text, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def _extract_cbm(text: str) -> Optional[float]:
    m = re.search(r"(?:CBM|M3|Volume|容積)[:\s]*([\d,\.]+)", text, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def _extract_container_type(text: str) -> str:
    patterns = [r"\b(20GP|40GP|40HC|20RF|40RF|LCL|BULK)\b"]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return ""


def _detect_base_currency(text: str) -> str:
    counts = {currency: 0 for currency in CURRENCY_PATTERNS}
    for currency, patterns in CURRENCY_PATTERNS.items():
        for pattern in patterns:
            counts[currency] += len(re.findall(pattern, text))
    return max(counts, key=counts.get) if any(counts.values()) else "JPY"


def _parse_tables(tables: list, full_text: str) -> List[ParsedCharge]:
    """테이블 구조에서 매출/매입 항목 추출"""
    charges = []

    for table in tables:
        if not table or len(table) < 2:
            continue

        # 헤더 행 찾기
        header_row = table[0] if table[0] else []
        header_text = " ".join([str(cell or "") for cell in header_row]).upper()

        # 매출/매입 구분 컬럼 인덱스 추정
        rev_col, cost_col = _find_revenue_cost_cols(header_row)

        for row in table[1:]:
            if not row or not any(row):
                continue

            row_text = " ".join([str(cell or "") for cell in row])

            # 비용 코드 감지
            charge_code, charge_name = _detect_charge_code(row_text)
            if not charge_code:
                continue

            # 금액 추출
            is_revenue, amount, currency = _extract_amount_from_row(
                row, rev_col, cost_col, row_text
            )

            if amount and amount > 0:
                charges.append(ParsedCharge(
                    charge_code=charge_code,
                    charge_name=charge_name,
                    is_revenue=is_revenue,
                    currency=currency,
                    amount=amount,
                    confidence=0.8,
                ))

    return charges


def _find_revenue_cost_cols(header_row: list) -> Tuple[int, int]:
    rev_col, cost_col = -1, -1
    for i, cell in enumerate(header_row):
        cell_str = str(cell or "").upper()
        if any(kw in cell_str for kw in ["REVENUE", "SELL", "売上", "CHARGE"]):
            rev_col = i
        if any(kw in cell_str for kw in ["COST", "BUY", "仕入", "PURCHASE"]):
            cost_col = i
    return rev_col, cost_col


def _detect_charge_code(text: str) -> Tuple[str, str]:
    text_upper = text.upper()
    for code, (name, _) in KNOWN_CHARGES.items():
        if re.search(r"\b" + re.escape(code) + r"\b", text_upper):
            return code, name
    return "", ""


def _extract_amount_from_row(
    row: list, rev_col: int, cost_col: int, row_text: str
) -> Tuple[bool, float, str]:
    """행에서 금액과 매출/매입 구분 추출"""
    currency = "JPY"

    # 통화 감지
    for cur, patterns in CURRENCY_PATTERNS.items():
        if any(re.search(p, row_text, re.IGNORECASE) for p in patterns):
            currency = cur
            break

    # 매출/매입 컬럼이 특정된 경우
    if rev_col >= 0 and rev_col < len(row):
        val = _parse_amount_str(str(row[rev_col] or ""))
        if val and val > 0:
            return True, val, currency

    if cost_col >= 0 and cost_col < len(row):
        val = _parse_amount_str(str(row[cost_col] or ""))
        if val and val > 0:
            return False, val, currency

    # 컬럼 특정 불가 → 키워드로 판단
    is_revenue = any(kw in row_text.upper() for kw in ["SELL", "REVENUE", "CHARGE"])

    # 숫자 추출
    amounts = AMOUNT_PATTERN.findall(row_text)
    for amount_str, _ in amounts:
        val = _parse_amount_str(amount_str)
        if val and val > 0:
            return is_revenue, val, currency

    return is_revenue, 0.0, currency


def _parse_amount_str(s: str) -> float:
    cleaned = re.sub(r"[¥$₩€,\s]", "", s)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _parse_text_charges(text: str) -> List[ParsedCharge]:
    """테이블 없을 때 텍스트에서 비용 항목 추출"""
    charges = []
    lines = text.split("\n")

    current_section_is_revenue: Optional[bool] = None

    for line in lines:
        line_upper = line.upper().strip()
        if not line_upper:
            continue

        # 섹션 전환 감지
        if any(kw in line_upper for kw in REVENUE_KEYWORDS):
            current_section_is_revenue = True
            continue
        if any(kw in line_upper for kw in COST_KEYWORDS):
            current_section_is_revenue = False
            continue

        # 비용 코드 감지
        charge_code, charge_name = _detect_charge_code(line)
        if not charge_code:
            continue

        # 금액 추출
        amounts = AMOUNT_PATTERN.findall(line)
        currency = "JPY"
        for cur, patterns in CURRENCY_PATTERNS.items():
            if any(re.search(p, line, re.IGNORECASE) for p in patterns):
                currency = cur
                break

        for amount_str, _ in amounts:
            val = _parse_amount_str(amount_str)
            if val and val > 0:
                is_revenue = current_section_is_revenue if current_section_is_revenue is not None else True
                charges.append(ParsedCharge(
                    charge_code=charge_code,
                    charge_name=charge_name,
                    is_revenue=is_revenue,
                    currency=currency,
                    amount=val,
                    confidence=0.6,  # 텍스트 기반 신뢰도 낮음
                ))
                break

    return charges
