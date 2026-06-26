"""
LOTOS AI 거래 분석 서비스
- Anthropic Claude API로 OCR 텍스트를 분석
- 거래 개요 / 자금 흐름 / 시사점 생성
- ANTHROPIC_API_KEY 환경변수 필요 (Railway Settings → Variables)
"""
import os
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 일본 포워딩(국제물류) 회사의 손익 분석 전문가입니다.
OCR로 추출한 Profit/Loss Sheet와 첨부 서류(Invoice, Packing List, 보험 서류 등)를 분석하여
아래 형식으로 한국어 분석 결과를 작성해 주세요.

출력 형식 (마크다운):
**[한 줄 요약 — 거래 성격과 마진 결과 포함]**

**거래 개요**
- 화주: [이름] → 수입자: [이름]
- 품목: [품목명 + 수량/중량]
- 선박: [선박명/항로] / [POL]→[POD], [ETD] 출항
- [기타 중요 정보 (보험, 계약조건 등)]

**자금 흐름 (LOTOS CORPORATION이 중개)**
| 구분 | 금액 |
|---|---|
| [수취처 이름]로부터 수취 | [금액] |
| [지급처 이름]에 지급 | [금액] |
| **마진(PROFIT)** | **[금액] (≈USD [USD환산])** |

**시사점**
- [이 거래의 비즈니스 구조와 특징]
- [리스크 또는 주목할 사항]
- [세무/승인/운영 관련 시사점]

주의사항:
- 수치는 OCR에서 읽은 값 그대로 사용 (가공 금지)
- 불확실한 내용은 추측하지 말고 "확인 필요" 표기
- 보험 거래, 운임 거래, 통관 거래 등 거래 유형을 명확히 구분
- 시사점은 포워더 실무자 관점에서 실용적으로 작성
"""


def analyze_transaction(ocr_text: str, hbl_no: str = "") -> str:
    """
    OCR 텍스트를 Claude API로 분석하여 마크다운 분석 결과 반환.
    API 키 없거나 실패 시 빈 문자열 반환 (업로드 자체는 중단 안 함).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("[ai_analyzer] ANTHROPIC_API_KEY 미설정 — AI 분석 스킵")
        return ""

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        user_message = f"""아래는 포워딩 Profit/Loss Sheet PDF를 OCR로 추출한 텍스트입니다.
H.B/L NO: {hbl_no or '(미확인)'}

=== OCR 텍스트 ===
{ocr_text[:6000]}
===================

위 내용을 분석하여 지정된 형식으로 거래 분석 결과를 작성해 주세요."""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        result = message.content[0].text if message.content else ""
        logger.info(f"[ai_analyzer] 분석 완료: {len(result)}자, hbl={hbl_no}")
        return result

    except ImportError:
        logger.error("[ai_analyzer] anthropic 패키지 미설치")
        return ""
    except Exception as e:
        logger.error(f"[ai_analyzer] Claude API 오류: {e}", exc_info=True)
        return ""
