"""
LOTOS AI 결재 엔진 — 4단계 판정 로직
판정 단계: APPROVED / CONDITIONAL / REVIEW / REJECTED
"""
from dataclasses import dataclass, field
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.transaction import ProfitSheetHeader, ProfitSheetDetail
from app.models.master import GpRuleMaster, PartnerFeeMaster, CustomerType
from app.models.result import ApprovalHistory, RuleEvaluationLog, Todo, TodoPriority


# ───────────────────────────────────────────────
# 자사 자원 활용 가능 구간 (PORT → 자사 서비스)
# ───────────────────────────────────────────────
INTERNAL_RESOURCE_ZONES = {
    "customs": ["TOKYO", "OSAKA", "NAGOYA", "YOKOHAMA", "KOBE"],
    "warehouse": ["TOKYO", "OSAKA"],
    "transport": ["TOKYO", "OSAKA"],
}

# 외부 통관비 코드
EXTERNAL_CUSTOMS_CHARGE_CODES = {"CUSTOMS", "CUS", "CUSTOMS_FEE", "外部通関"}

# 비용 누락 의심 쌍 (매입에 있으면 매출에도 있어야 할 항목)
EXPECTED_REVENUE_PAIRS = {
    "THC": "THC",
    "BAF": "BAF",
    "WAF": "WAF",
    "DOC": "DOC",
    "AFR": "AFR",
    "AMS": "AMS",
}


@dataclass
class RuleResult:
    rule_code: str
    rule_name: str
    passed: bool
    input_value: str = ""
    threshold_value: str = ""
    message: str = ""


@dataclass
class ApprovalResult:
    judgment: str          # APPROVED / CONDITIONAL / REVIEW / REJECTED
    rule_results: List[RuleResult] = field(default_factory=list)
    todos: List[dict] = field(default_factory=list)
    summary: str = ""


def run_approval(
    header: ProfitSheetHeader,
    details: List[ProfitSheetDetail],
    db: Session,
) -> ApprovalResult:
    """메인 결재 판정 함수"""
    rule_results: List[RuleResult] = []
    todos: List[dict] = []

    # 1. GP 검증
    gp_result = _check_gp(header, db)
    rule_results.append(gp_result)
    if not gp_result.passed:
        todos.append({
            "title": f"GP 기준 미달 — {gp_result.message}",
            "rule_code": "GP_CHECK",
            "priority": TodoPriority.HIGH,
        })

    # 2. Partner Fee 검증
    fee_result = _check_partner_fee(header, details, db)
    rule_results.append(fee_result)
    if not fee_result.passed:
        todos.append({
            "title": f"파트너 Fee 초과 — {fee_result.message}",
            "rule_code": "PARTNER_FEE",
            "priority": TodoPriority.HIGH,
        })

    # 3. 자사 자원 활용 검증
    resource_result = _check_internal_resource(header, details)
    rule_results.append(resource_result)
    if not resource_result.passed:
        todos.append({
            "title": f"자사 자원 미활용 — {resource_result.message}",
            "rule_code": "INTERNAL_RESOURCE",
            "priority": TodoPriority.HIGH,
        })

    # 4. 비용 누락 검증
    omission_results = _check_cost_omission(details)
    rule_results.extend(omission_results)
    for r in omission_results:
        if not r.passed:
            todos.append({
                "title": f"비용 누락 의심 — {r.message}",
                "rule_code": "COST_OMISSION",
                "priority": TodoPriority.MEDIUM,
            })

    # 최종 판정
    judgment = _determine_judgment(rule_results, resource_result)

    return ApprovalResult(
        judgment=judgment,
        rule_results=rule_results,
        todos=todos,
        summary=_build_summary(judgment, rule_results),
    )


def _check_gp(header: ProfitSheetHeader, db: Session) -> RuleResult:
    """GP 기준 검증 룰"""
    gp = header.gp_jpy or 0.0
    gp_rate = header.gp_rate or 0.0
    revenue = header.total_revenue_jpy or 0.0
    customer_type = header.customer_type

    # 거래처 유형별 GP율 기준
    type_rate_map = {
        "SHIPPER": 15.0,
        "FORWARDER": 10.0,
        "PARTNER": 5.0,
    }

    # 기본 SI 건 최소 GP
    is_si = str(header.job_code).startswith("SI")
    if is_si and gp < 8000:
        return RuleResult(
            rule_code="GP_CHECK",
            rule_name="SI 최소 GP 검증",
            passed=False,
            input_value=f"GP {gp:,.0f}엔",
            threshold_value="최소 8,000엔",
            message=f"SI 건 최소 GP 8,000엔 미달 (현재: {gp:,.0f}엔)",
        )

    # 매출 구간별 GP 검증
    if revenue <= 30_000:
        if gp < 3_000:
            return RuleResult(
                rule_code="GP_CHECK",
                rule_name="매출 3만엔 이하 구간 GP 검증",
                passed=False,
                input_value=f"GP {gp:,.0f}엔",
                threshold_value="최소 3,000엔",
                message=f"매출 3만엔 이하 구간 — GP {gp:,.0f}엔 (최소 3,000엔 필요)",
            )
    elif revenue <= 80_000:
        if gp < 5_000:
            return RuleResult(
                rule_code="GP_CHECK",
                rule_name="매출 3~8만엔 구간 GP 검증",
                passed=False,
                input_value=f"GP {gp:,.0f}엔",
                threshold_value="최소 5,000엔",
                message=f"매출 3~8만엔 구간 — GP {gp:,.0f}엔 (최소 5,000엔 필요)",
            )
    else:
        if gp_rate < 10.0:
            return RuleResult(
                rule_code="GP_CHECK",
                rule_name="매출 8만엔 초과 구간 GP율 검증",
                passed=False,
                input_value=f"GP율 {gp_rate:.1f}%",
                threshold_value="최소 10%",
                message=f"매출 8만엔 초과 구간 — GP율 {gp_rate:.1f}% (최소 10% 필요)",
            )

    # 거래처 유형별 GP율 검증
    if customer_type and customer_type in type_rate_map:
        target_rate = type_rate_map[customer_type]
        if gp_rate < target_rate:
            return RuleResult(
                rule_code="GP_CHECK",
                rule_name=f"{customer_type} GP율 검증",
                passed=False,
                input_value=f"GP율 {gp_rate:.1f}%",
                threshold_value=f"목표 {target_rate}%",
                message=f"{customer_type} 건 GP율 {gp_rate:.1f}% (목표: {target_rate}%)",
            )

    return RuleResult(
        rule_code="GP_CHECK",
        rule_name="GP 기준 검증",
        passed=True,
        input_value=f"GP {gp:,.0f}엔 / {gp_rate:.1f}%",
        message="GP 기준 충족",
    )


def _check_partner_fee(
    header: ProfitSheetHeader,
    details: List[ProfitSheetDetail],
    db: Session,
) -> RuleResult:
    """Partner Fee 상한 검증"""
    if not header.partner_name:
        return RuleResult(
            rule_code="PARTNER_FEE",
            rule_name="Partner Fee 검증",
            passed=True,
            message="파트너 없음 — 검증 생략",
        )

    # 파트너 매입 합계
    partner_costs = [
        d for d in details
        if not d.is_revenue and d.partner_name == header.partner_name
    ]
    total_partner_fee_jpy = sum(d.amount_jpy or 0 for d in partner_costs)

    # DB에서 파트너별 상한 조회
    fee_rule = (
        db.query(PartnerFeeMaster)
        .filter(
            PartnerFeeMaster.partner_name == header.partner_name,
            PartnerFeeMaster.is_active == True,
        )
        .first()
    )

    max_fee = fee_rule.max_fee_jpy if fee_rule and fee_rule.max_fee_jpy else 4_000  # 기본 4,000엔

    if total_partner_fee_jpy > max_fee:
        return RuleResult(
            rule_code="PARTNER_FEE",
            rule_name="Partner Fee 상한 검증",
            passed=False,
            input_value=f"{total_partner_fee_jpy:,.0f}엔",
            threshold_value=f"상한 {max_fee:,.0f}엔",
            message=f"{header.partner_name} Fee {total_partner_fee_jpy:,.0f}엔 초과 (상한: {max_fee:,.0f}엔)",
        )

    return RuleResult(
        rule_code="PARTNER_FEE",
        rule_name="Partner Fee 상한 검증",
        passed=True,
        input_value=f"{total_partner_fee_jpy:,.0f}엔",
        threshold_value=f"상한 {max_fee:,.0f}엔",
        message="Partner Fee 기준 충족",
    )


def _check_internal_resource(
    header: ProfitSheetHeader,
    details: List[ProfitSheetDetail],
) -> RuleResult:
    """자사 자원 활용 검증 — 가능 구간에서 외부 위탁 시 경고"""
    origin = (header.origin_port or "").upper()
    dest = (header.dest_port or "").upper()

    # 자사 통관 가능 PORT에서 외부 통관비 지출 여부 확인
    for port in [origin, dest]:
        if port in INTERNAL_RESOURCE_ZONES["customs"]:
            external_customs = [
                d for d in details
                if not d.is_revenue
                and d.charge_code.upper() in EXTERNAL_CUSTOMS_CHARGE_CODES
            ]
            if external_customs:
                total = sum(d.amount_jpy or 0 for d in external_customs)
                return RuleResult(
                    rule_code="INTERNAL_RESOURCE",
                    rule_name="자사 통관 자원 활용 검증",
                    passed=False,
                    input_value=f"외부 통관비 {total:,.0f}엔 지출",
                    threshold_value="자사 통관 가능 구간",
                    message=f"{port} 구간 자사 통관 가능 — 외부 통관비 {total:,.0f}엔 지출 (사유 등록 필요)",
                )

    return RuleResult(
        rule_code="INTERNAL_RESOURCE",
        rule_name="자사 자원 활용 검증",
        passed=True,
        message="자사 자원 활용 기준 충족",
    )


def _check_cost_omission(details: List[ProfitSheetDetail]) -> List[RuleResult]:
    """비용 누락 검증 — 매입에 있으나 매출에 없는 항목 스캔"""
    results = []
    revenue_codes = {d.charge_code.upper() for d in details if d.is_revenue}
    cost_codes = {d.charge_code.upper() for d in details if not d.is_revenue}

    for cost_code, expected_rev_code in EXPECTED_REVENUE_PAIRS.items():
        if cost_code in cost_codes and expected_rev_code not in revenue_codes:
            results.append(RuleResult(
                rule_code="COST_OMISSION",
                rule_name=f"{cost_code} 매출 누락 검증",
                passed=False,
                input_value=f"매입 {cost_code} 존재",
                threshold_value=f"매출 {expected_rev_code} 필요",
                message=f"매입 {cost_code} 있으나 매출 청구 누락 의심",
            ))

    if not results:
        results.append(RuleResult(
            rule_code="COST_OMISSION",
            rule_name="비용 누락 검증",
            passed=True,
            message="비용 누락 없음",
        ))

    return results


def _determine_judgment(rule_results: List[RuleResult], resource_result: RuleResult) -> str:
    """최종 판정 결정"""
    # 자사 자원 미활용 → 무조건 REJECTED (GP 우수해도)
    if not resource_result.passed:
        return "REJECTED"

    failed = [r for r in rule_results if not r.passed]

    if not failed:
        return "APPROVED"

    # GP 실패 → REVIEW
    gp_failed = any(r.rule_code == "GP_CHECK" and not r.passed for r in rule_results)
    if gp_failed:
        return "REVIEW"

    # Partner Fee 실패 → REJECTED
    fee_failed = any(r.rule_code == "PARTNER_FEE" and not r.passed for r in rule_results)
    if fee_failed:
        return "REJECTED"

    # 비용 누락만 있는 경우 → CONDITIONAL
    return "CONDITIONAL"


def _build_summary(judgment: str, rule_results: List[RuleResult]) -> str:
    label_map = {
        "APPROVED": "✅ 승인 가능",
        "CONDITIONAL": "🟡 조건부 승인",
        "REVIEW": "🟠 검토 필요",
        "REJECTED": "🔴 부적합",
    }
    failed = [r.message for r in rule_results if not r.passed]
    label = label_map.get(judgment, judgment)
    if failed:
        return f"{label} — {'; '.join(failed)}"
    return label


def calculate_rt(weight_kg: Optional[float], cbm: Optional[float]) -> float:
    """RT 계산: weight_ton vs CBM 중 큰 값"""
    weight_ton = (weight_kg or 0) / 1000
    volume_ton = cbm or 0
    return max(weight_ton, volume_ton)
