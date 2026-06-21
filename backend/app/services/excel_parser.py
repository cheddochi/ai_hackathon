"""
Excel Profit Sheet 파서
openpyxl 기반으로 .xlsx 파일에서 매출/매입 항목 추출
"""
from dataclasses import dataclass, field
from typing import List, Optional
import openpyxl
from app.services.pdf_parser import ParsedCharge, ParsedProfitSheet, KNOWN_CHARGES


HEADER_ALIASES = {
    "charge_code": ["코드", "CODE", "항목코드", "CHARGE CODE", "ITEM"],
    "charge_name": ["항목명", "NAME", "DESCRIPTION", "DESC", "명칭"],
    "revenue": ["매출", "REVENUE", "SELL", "売上", "CHARGE"],
    "cost": ["매입", "COST", "BUY", "仕入", "PURCHASE"],
    "currency": ["통화", "CURRENCY", "CCY"],
    "partner": ["파트너", "PARTNER", "VENDOR", "업체"],
    "unit": ["단위", "UNIT", "QTY"],
}


def parse_excel(file_path: str) -> ParsedProfitSheet:
    """Excel 파일을 파싱하여 ParsedProfitSheet 반환"""
    result = ParsedProfitSheet()

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
    except Exception as e:
        result.parse_warnings.append(f"Excel 파일 열기 실패: {str(e)}")
        return result

    # 첫 번째 시트 또는 'Profit', 'P&L' 이름 시트 우선
    target_sheet = None
    for name in wb.sheetnames:
        if any(k in name.upper() for k in ["PROFIT", "P&L", "PL", "손익"]):
            target_sheet = wb[name]
            break
    if target_sheet is None:
        target_sheet = wb.active

    rows = list(target_sheet.iter_rows(values_only=True))
    if not rows:
        result.parse_warnings.append("시트에 데이터가 없습니다.")
        return result

    # 메타 정보 추출 (상단 영역 스캔)
    result = _extract_meta_from_excel(rows, result)

    # 헤더 행 찾기
    header_row_idx, col_map = _find_header_row(rows)

    if header_row_idx < 0 or not col_map:
        # 헤더 없으면 텍스트 기반 추출 시도
        result.charges = _fallback_parse(rows)
        result.parse_warnings.append("헤더 자동 감지 실패 — 패턴 기반 파싱 사용")
        return result

    # 데이터 행 파싱
    charges = []
    for row in rows[header_row_idx + 1:]:
        if not row or not any(row):
            continue
        charge = _parse_data_row(row, col_map)
        if charge:
            charges.append(charge)

    result.charges = charges
    return result


def _extract_meta_from_excel(rows: list, result: ParsedProfitSheet) -> ParsedProfitSheet:
    """상단 영역에서 메타 정보 추출"""
    for row in rows[:20]:  # 상단 20행만 스캔
        for i, cell in enumerate(row):
            if cell is None:
                continue
            cell_str = str(cell).strip()
            next_val = str(row[i + 1]).strip() if i + 1 < len(row) and row[i + 1] else ""

            cell_upper = cell_str.upper()
            if any(k in cell_upper for k in ["CASE", "案件", "안건"]) and next_val:
                result.case_no = next_val
            elif any(k in cell_upper for k in ["CUSTOMER", "顧客", "거래처", "SHIPPER"]) and next_val:
                result.customer_name = next_val
            elif any(k in cell_upper for k in ["ASSIGNEE", "담당", "担当"]) and next_val:
                result.assignee_name = next_val
            elif any(k in cell_upper for k in ["FROM", "ORIGIN", "POL", "출발"]) and next_val:
                result.origin_port = next_val.upper()
            elif any(k in cell_upper for k in ["TO", "DEST", "POD", "도착"]) and next_val:
                result.dest_port = next_val.upper()
            elif any(k in cell_upper for k in ["WEIGHT", "G.W", "중량"]) and next_val:
                try:
                    result.weight_kg = float(str(next_val).replace(",", ""))
                except ValueError:
                    pass
            elif "CBM" in cell_upper and next_val:
                try:
                    result.cbm = float(str(next_val).replace(",", ""))
                except ValueError:
                    pass
    return result


def _find_header_row(rows: list):
    """헤더 행 및 컬럼 매핑 탐지"""
    for idx, row in enumerate(rows):
        if not row or not any(row):
            continue
        row_strs = [str(c or "").upper().strip() for c in row]
        col_map = {}

        # 매출/매입 컬럼 존재 여부로 헤더 판단
        has_revenue = False
        has_cost = False

        for col_idx, cell_str in enumerate(row_strs):
            for field_name, aliases in HEADER_ALIASES.items():
                if any(alias.upper() in cell_str for alias in aliases):
                    if field_name not in col_map:
                        col_map[field_name] = col_idx
                    if field_name == "revenue":
                        has_revenue = True
                    if field_name == "cost":
                        has_cost = True

        if has_revenue or has_cost:
            return idx, col_map

    return -1, {}


def _parse_data_row(row: tuple, col_map: dict) -> Optional[ParsedCharge]:
    """단일 데이터 행 파싱"""
    def get_cell(field_name):
        idx = col_map.get(field_name)
        if idx is not None and idx < len(row):
            return row[idx]
        return None

    # 비용 코드 추출
    code_raw = str(get_cell("charge_code") or "").strip().upper()
    name_raw = str(get_cell("charge_name") or "").strip()

    if not code_raw and not name_raw:
        return None

    # 알려진 코드 매핑
    charge_code = code_raw
    charge_name = name_raw
    if code_raw in KNOWN_CHARGES:
        charge_name = charge_name or KNOWN_CHARGES[code_raw][0]
    elif name_raw:
        # 이름으로 코드 역조회
        for code, (en_name, _) in KNOWN_CHARGES.items():
            if en_name.upper() in name_raw.upper() or code in name_raw.upper():
                charge_code = code
                charge_name = charge_name or en_name
                break

    if not charge_code:
        return None

    # 매출/매입 금액
    rev_val = _to_float(get_cell("revenue"))
    cost_val = _to_float(get_cell("cost"))

    if rev_val and rev_val > 0:
        is_revenue = True
        amount = rev_val
    elif cost_val and cost_val > 0:
        is_revenue = False
        amount = cost_val
    else:
        return None

    currency = str(get_cell("currency") or "JPY").strip().upper() or "JPY"
    partner = str(get_cell("partner") or "").strip()
    unit = str(get_cell("unit") or "").strip()

    return ParsedCharge(
        charge_code=charge_code,
        charge_name=charge_name,
        is_revenue=is_revenue,
        currency=currency,
        amount=amount,
        partner_name=partner,
        unit=unit,
        confidence=0.9,
    )


def _fallback_parse(rows: list) -> List[ParsedCharge]:
    """헤더 감지 실패 시 전체 셀 스캔"""
    charges = []
    for row in rows:
        if not row:
            continue
        row_text = " ".join(str(c or "") for c in row)
        for code, (name, _) in KNOWN_CHARGES.items():
            if code in row_text.upper():
                for cell in row:
                    try:
                        val = float(str(cell).replace(",", ""))
                        if val > 0:
                            charges.append(ParsedCharge(
                                charge_code=code,
                                charge_name=name,
                                is_revenue=True,
                                currency="JPY",
                                amount=val,
                                confidence=0.4,
                            ))
                            break
                    except (ValueError, TypeError):
                        continue
    return charges


def _to_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
