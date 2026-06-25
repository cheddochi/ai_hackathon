"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import { profitSheetApi, approvalApi, masterApi } from "@/lib/api";
import {
  CheckCircle, XCircle, AlertCircle, Clock, ChevronLeft,
  Trash2, ThumbsUp, ThumbsDown, RefreshCw, Loader2,
} from "lucide-react";
import clsx from "clsx";

const JUDGMENT_CONFIG: Record<string, { label: string; color: string; bg: string; icon: typeof CheckCircle }> = {
  APPROVED:    { label: "승인 가능",   color: "text-success",      bg: "bg-green-50 border-success",       icon: CheckCircle },
  CONDITIONAL: { label: "조건부 승인", color: "text-warning",      bg: "bg-yellow-50 border-warning",      icon: AlertCircle },
  REVIEW:      { label: "검토 필요",   color: "text-orange-500",   bg: "bg-orange-50 border-orange-400",   icon: AlertCircle },
  REJECTED:    { label: "부적합",      color: "text-danger",       bg: "bg-red-50 border-danger",          icon: XCircle },
};

const RULE_LABELS: Record<string, string> = {
  GP_CHECK: "GP 기준 검증",
  PARTNER_FEE: "Partner Fee 검증",
  INTERNAL_RESOURCE: "자사 자원 활용",
  COST_OMISSION: "비용 누락 검증",
};

// ── 통화 포맷 유틸 ────────────────────────────────────────────
const CURRENCY_SYMBOL: Record<string, string> = { USD: "$", JPY: "¥", KRW: "₩" };

function fmtOrig(amount: number, currency: string): string {
  return `${CURRENCY_SYMBOL[currency] || ""}${Math.round(amount).toLocaleString("ko-KR")}`;
}
function fmtKrw(n: number): string {
  return `₩${Math.round(n).toLocaleString("ko-KR")}`;
}
function amountToKrw(d: any, krwPerJpy: number): number {
  if (d.currency === "KRW") return d.amount;
  return (d.amount_jpy ?? 0) * krwPerJpy;
}

function TrafficLight({ passed, label }: { passed: boolean | null; label: string }) {
  if (passed === null) return null;
  return (
    <div className="flex items-center gap-2">
      <div className={clsx("w-3 h-3 rounded-full", passed ? "bg-success" : "bg-danger")} />
      <span className="text-xs text-gray-600">{label}</span>
    </div>
  );
}

// ── 인간 결재 패널 ────────────────────────────────────────────
function HumanDecisionPanel({
  sheet,
  onUpdated,
}: {
  sheet: any;
  onUpdated: (updated: any) => void;
}) {
  const hasDecision = !!sheet.human_decision;
  const [mode, setMode] = useState<"view" | "edit">(hasDecision ? "view" : "edit");
  const [decision, setDecision] = useState<"APPROVED" | "REJECTED" | null>(
    sheet.human_decision || null
  );
  const [comment, setComment] = useState(sheet.human_comment || "");
  const [krwRate, setKrwRate] = useState<string>(sheet.exchange_rate_krw?.toString() || "");
  const [usdRate, setUsdRate] = useState<string>(sheet.exchange_rate_usd?.toString() || "");
  const [rateNote, setRateNote] = useState<string>(sheet.exchange_rate_note || "");
  const [fetchingRate, setFetchingRate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [rateError, setRateError] = useState<string | null>(null);

  // 환율 자동 조회 (SMBS)
  const handleFetchRate = async () => {
    setFetchingRate(true);
    setRateError(null);
    try {
      const res = await masterApi.todayExchangeRate();
      const { jpy_krw, usd_jpy, fetched_at, source } = res.data;
      if (jpy_krw) setKrwRate(jpy_krw.toFixed(4));
      if (usd_jpy) setUsdRate(usd_jpy.toFixed(2));
      const dateStr = fetched_at ? new Date(fetched_at).toLocaleString("ko-KR") : "";
      setRateNote(`${source} ${dateStr} 기준`);
    } catch (e: any) {
      setRateError(e?.response?.data?.detail || "환율 조회에 실패했습니다. 수동으로 입력해 주세요.");
    } finally {
      setFetchingRate(false);
    }
  };

  // 결재 저장
  const handleSave = async () => {
    if (!decision) {
      alert("승인 또는 반려를 선택해 주세요.");
      return;
    }
    setSaving(true);
    try {
      const res = await profitSheetApi.updateDecision(sheet.id, {
        decision,
        comment: comment.trim() || undefined,
        exchange_rate_krw: krwRate ? parseFloat(krwRate) : undefined,
        exchange_rate_usd: usdRate ? parseFloat(usdRate) : undefined,
        exchange_rate_note: rateNote.trim() || undefined,
      });
      onUpdated(res.data);
      setMode("view");
    } catch {
      alert("저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  // 결재 해제
  const handleClear = async () => {
    if (!confirm("결재를 해제하시겠습니까?")) return;
    setSaving(true);
    try {
      const res = await profitSheetApi.updateDecision(sheet.id, { decision: null });
      onUpdated(res.data);
      setDecision(null);
      setComment("");
      setMode("edit");
    } catch {
      alert("해제에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  // ── view mode (결재 완료 상태) ──────────────────────────────
  if (mode === "view" && sheet.human_decision) {
    const isApproved = sheet.human_decision === "APPROVED";
    return (
      <div className={clsx(
        "rounded-xl border-2 p-4",
        isApproved ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"
      )}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {isApproved
              ? <ThumbsUp size={18} className="text-green-600" />
              : <ThumbsDown size={18} className="text-red-500" />
            }
            <span className={clsx("font-semibold text-sm", isApproved ? "text-green-700" : "text-red-600")}>
              {isApproved ? "승인됨" : "반려됨"}
            </span>
          </div>
          <div className="flex gap-1.5">
            <button
              onClick={() => setMode("edit")}
              className="text-xs px-2 py-1 bg-white border border-gray-200 rounded hover:bg-gray-50 text-gray-600"
            >
              수정
            </button>
            <button
              onClick={handleClear}
              disabled={saving}
              className="text-xs px-2 py-1 bg-white border border-red-200 rounded hover:bg-red-50 text-red-500 disabled:opacity-40"
            >
              해제
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 mb-2">
          {sheet.human_decided_by} · {sheet.human_decided_at ? new Date(sheet.human_decided_at).toLocaleString("ko-KR") : "—"}
        </p>
        {sheet.human_comment && (
          <p className="text-sm text-gray-700 bg-white/70 rounded p-2 whitespace-pre-wrap leading-relaxed">
            {sheet.human_comment}
          </p>
        )}
        {sheet.exchange_rate_note && (
          <p className="mt-2 text-xs text-gray-400">
            📊 {sheet.exchange_rate_note}
          </p>
        )}
      </div>
    );
  }

  // ── edit mode (결재 입력) ───────────────────────────────────
  return (
    <div className="space-y-4">
      {/* 환율 설정 */}
      <div className="bg-gray-50 rounded-lg p-3 space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-gray-600">계약 시점 환율</p>
          <button
            onClick={handleFetchRate}
            disabled={fetchingRate}
            className="flex items-center gap-1 text-xs text-accent hover:text-accent/80 disabled:opacity-50"
          >
            {fetchingRate
              ? <Loader2 size={12} className="animate-spin" />
              : <RefreshCw size={12} />
            }
            {fetchingRate ? "조회 중..." : "SMBS 자동조회"}
          </button>
        </div>
        {rateError && (
          <p className="text-xs text-red-500">{rateError}</p>
        )}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-gray-400 block mb-1">JPY → KRW</label>
            <input
              type="number"
              step="0.0001"
              value={krwRate}
              onChange={(e) => setKrwRate(e.target.value)}
              placeholder="예: 9.31"
              className="w-full text-sm border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-accent bg-white"
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">USD → JPY</label>
            <input
              type="number"
              step="0.01"
              value={usdRate}
              onChange={(e) => setUsdRate(e.target.value)}
              placeholder="예: 148.50"
              className="w-full text-sm border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-accent bg-white"
            />
          </div>
        </div>
        {rateNote && (
          <p className="text-xs text-gray-400 truncate">📊 {rateNote}</p>
        )}
      </div>

      {/* 승인 / 반려 선택 */}
      <div>
        <p className="text-xs font-semibold text-gray-600 mb-2">결재 선택</p>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => setDecision("APPROVED")}
            className={clsx(
              "flex items-center justify-center gap-2 py-2.5 rounded-lg border-2 text-sm font-medium transition-all",
              decision === "APPROVED"
                ? "border-green-500 bg-green-50 text-green-700"
                : "border-gray-200 bg-white text-gray-500 hover:border-green-300 hover:bg-green-50/50"
            )}
          >
            <ThumbsUp size={15} /> 승인
          </button>
          <button
            onClick={() => setDecision("REJECTED")}
            className={clsx(
              "flex items-center justify-center gap-2 py-2.5 rounded-lg border-2 text-sm font-medium transition-all",
              decision === "REJECTED"
                ? "border-red-500 bg-red-50 text-red-600"
                : "border-gray-200 bg-white text-gray-500 hover:border-red-300 hover:bg-red-50/50"
            )}
          >
            <ThumbsDown size={15} /> 반려
          </button>
        </div>
      </div>

      {/* 의견 입력 */}
      <div>
        <label className="text-xs font-semibold text-gray-600 block mb-1">
          결재 의견 <span className="text-gray-400 font-normal">(선택)</span>
        </label>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="승인/반려 사유, 조건, 특이사항을 입력하세요..."
          rows={3}
          className="w-full text-sm border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-accent resize-none"
        />
      </div>

      {/* 액션 버튼 */}
      <div className="flex gap-2">
        {mode === "edit" && sheet.human_decision && (
          <button
            onClick={() => setMode("view")}
            className="flex-1 btn-secondary text-sm"
          >
            취소
          </button>
        )}
        <button
          onClick={handleSave}
          disabled={saving || !decision}
          className={clsx(
            "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-semibold transition-colors disabled:opacity-40",
            decision === "APPROVED"
              ? "bg-green-600 hover:bg-green-700 text-white"
              : decision === "REJECTED"
              ? "bg-red-500 hover:bg-red-600 text-white"
              : "bg-gray-300 text-gray-500 cursor-not-allowed"
          )}
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : null}
          {saving ? "저장 중..." : "결재 저장"}
        </button>
      </div>
    </div>
  );
}

// ── 항목 테이블 ───────────────────────────────────────────────
function ChargeTable({ rows, krwPerJpy }: { rows: any[]; krwPerJpy: number }) {
  if (rows.length === 0) return <p className="text-xs text-gray-400 py-2">항목 없음</p>;

  const currencySums: Record<string, number> = {};
  rows.forEach((d) => { currencySums[d.currency] = (currencySums[d.currency] || 0) + (d.amount || 0); });

  return (
    <div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-100">
            <th className="text-left py-2 text-gray-400">코드</th>
            <th className="text-left py-2 text-gray-400">항목명</th>
            <th className="text-left py-2 text-gray-400">파트너</th>
            <th className="text-center py-2 text-gray-400">통화</th>
            <th className="text-right py-2 text-gray-400">원래 금액</th>
            <th className="text-right py-2 text-gray-400">원화 환산(₩)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d: any, i: number) => (
            <tr key={i} className={clsx("border-b border-gray-50", d.is_missing_flag && "bg-yellow-50")}>
              <td className="py-2 font-mono font-medium">{d.charge_code}</td>
              <td className="py-2 text-gray-600">{d.charge_name || "—"}</td>
              <td className="py-2 text-gray-500">{d.partner_name || "—"}</td>
              <td className="py-2 text-center">
                <span className={clsx(
                  "px-1.5 py-0.5 rounded text-xs font-mono font-semibold",
                  d.currency === "USD" && "bg-blue-100 text-blue-700",
                  d.currency === "JPY" && "bg-orange-100 text-orange-700",
                  d.currency === "KRW" && "bg-green-100 text-green-700",
                )}>
                  {d.currency}
                </span>
              </td>
              <td className="py-2 text-right font-medium">{fmtOrig(d.amount || 0, d.currency)}</td>
              <td className="py-2 text-right text-gray-700">
                {d.currency === "KRW"
                  ? <span className="text-gray-400">—</span>
                  : fmtKrw(amountToKrw(d, krwPerJpy))
                }
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {Object.keys(currencySums).length > 1 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {Object.entries(currencySums).map(([cur, sum]) => (
            <span key={cur} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
              {fmtOrig(sum, cur)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 메인 페이지 ──────────────────────────────────────────────
export default function ApprovalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [sheet, setSheet] = useState<any>(null);
  const [approval, setApproval] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    profitSheetApi.get(Number(id)).then((r) => setSheet(r.data));
    approvalApi.history(Number(id)).then((r) => {
      if (r.data.length > 0) setApproval(r.data[0]);
    });
  }, [id]);

  const handleRunApproval = async () => {
    setRunning(true);
    try {
      const res = await approvalApi.run(Number(id));
      setApproval(res.data);
      const r2 = await profitSheetApi.get(Number(id));
      setSheet(r2.data);
    } catch {
      alert("결재 실행 실패");
    } finally {
      setRunning(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`안건 "${sheet.case_no}"를 삭제하시겠습니까?\n삭제 후 복구가 불가능합니다.`)) return;
    setDeleting(true);
    try {
      await profitSheetApi.delete(Number(id));
      router.push("/profit-sheet");
    } catch {
      alert("삭제에 실패했습니다.");
      setDeleting(false);
    }
  };

  if (!sheet) return <div className="p-6 text-sm text-gray-400">로딩 중...</div>;

  const cfg = approval ? JUDGMENT_CONFIG[approval.judgment] : null;
  const krwPerJpy = sheet.exchange_rate_krw || 9.5;
  const revenueKrw = (sheet.total_revenue_jpy || 0) * krwPerJpy;
  const costKrw    = (sheet.total_cost_jpy    || 0) * krwPerJpy;
  const gpKrw      = (sheet.gp_jpy            || 0) * krwPerJpy;

  const revenues = (sheet.details || []).filter((d: any) =>  d.is_revenue);
  const costs    = (sheet.details || []).filter((d: any) => !d.is_revenue);

  return (
    <div>
      <Header title={`안건 심사 — ${sheet.case_no || `#${id}`}`} />
      <div className="p-6 space-y-6 max-w-5xl">
        {/* 뒤로 + 삭제 */}
        <div className="flex items-center justify-between">
          <button onClick={() => router.back()} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
            <ChevronLeft size={16} /> 목록으로
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="flex items-center gap-1.5 text-sm text-red-500 hover:text-red-700 hover:bg-red-50 px-3 py-1.5 rounded transition-colors disabled:opacity-40"
          >
            <Trash2 size={14} />
            {deleting ? "삭제 중..." : "안건 삭제"}
          </button>
        </div>

        <div className="grid grid-cols-3 gap-6">
          {/* 좌: 안건 정보 + 매출/매입 */}
          <div className="col-span-2 space-y-4">
            {/* 메타 */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-gray-700">안건 기본 정보</h2>
                <span className="font-mono text-xs bg-accent-light text-accent px-2 py-1 rounded">
                  {sheet.job_code}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-x-6 gap-y-3 text-sm">
                {[
                  ["거래처", sheet.customer_name],
                  ["거래처 구분", sheet.customer_type],
                  ["파트너", sheet.partner_name],
                  ["담당자", sheet.assignee_name],
                  ["출발지", sheet.origin_port],
                  ["도착지", sheet.dest_port],
                  ["중량", sheet.weight_kg ? `${sheet.weight_kg.toLocaleString()} KG` : "—"],
                  ["CBM", sheet.cbm ?? "—"],
                  ["RT", sheet.rt?.toFixed(2) ?? "—"],
                  ["컨테이너", sheet.container_type || "—"],
                  ["입력방식", sheet.input_method],
                  ["환율 (JPY→KRW)", krwPerJpy ? `${krwPerJpy}` : "—"],
                ].map(([label, value]) => (
                  <div key={label}>
                    <p className="text-xs text-gray-400">{label}</p>
                    <p className="font-medium text-gray-800">{value || "—"}</p>
                  </div>
                ))}
              </div>
              {sheet.exchange_rate_note && (
                <p className="mt-3 text-xs text-gray-400 border-t border-gray-100 pt-3">
                  📊 {sheet.exchange_rate_note}
                </p>
              )}
            </div>

            {/* GP 요약 */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-gray-700">수익성 요약</h2>
                <span className="text-xs text-gray-400">원화(₩) 기준 · {krwPerJpy} KRW/JPY</span>
              </div>
              <div className="grid grid-cols-3 gap-4">
                {[
                  { label: "총 매출", value: revenueKrw, color: "text-gray-900" },
                  { label: "총 매입", value: costKrw,    color: "text-danger" },
                  { label: "GP",      value: gpKrw,      color: "text-success" },
                ].map((item) => (
                  <div key={item.label} className="text-center p-4 bg-gray-50 rounded-lg">
                    <p className="text-xs text-gray-400 mb-1">{item.label}</p>
                    <p className={clsx("text-lg font-semibold", item.color)}>{fmtKrw(item.value)}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 text-center">
                <p className="text-xs text-gray-400">GP율</p>
                <p className="text-2xl font-bold text-accent">
                  {sheet.gp_rate != null ? `${sheet.gp_rate.toFixed(1)}%` : "—"}
                </p>
              </div>
            </div>

            {/* 매출 항목 */}
            <div className="card">
              <h2 className="text-sm font-semibold text-gray-700 mb-3">
                매출 항목
                <span className="ml-2 text-xs font-normal text-gray-400">원래 통화 + 원화 환산</span>
              </h2>
              <ChargeTable rows={revenues} krwPerJpy={krwPerJpy} />
              {revenues.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-100 flex justify-end text-xs font-semibold text-gray-700">
                  합계: {fmtKrw(revenueKrw)}
                </div>
              )}
            </div>

            {/* 매입 항목 */}
            <div className="card">
              <h2 className="text-sm font-semibold text-gray-700 mb-3">
                매입 항목
                <span className="ml-2 text-xs font-normal text-gray-400">원래 통화 + 원화 환산</span>
              </h2>
              <ChargeTable rows={costs} krwPerJpy={krwPerJpy} />
              {costs.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-100 flex justify-end text-xs font-semibold text-danger">
                  합계: {fmtKrw(costKrw)}
                </div>
              )}
            </div>
          </div>

          {/* 우: 결재 패널 */}
          <div className="space-y-4">
            {/* AI 결재 결과 */}
            {cfg && (
              <div className={clsx("card border-2", cfg.bg)}>
                <p className="text-xs font-semibold text-gray-400 mb-2">AI 판정</p>
                <div className="flex items-center gap-2 mb-3">
                  <cfg.icon size={20} className={cfg.color} />
                  <span className={clsx("font-semibold text-base", cfg.color)}>{cfg.label}</span>
                </div>
                <div className="space-y-2 mb-4">
                  <TrafficLight passed={approval.gp_rule_passed} label="GP 기준" />
                  <TrafficLight passed={approval.partner_fee_passed} label="Partner Fee" />
                  <TrafficLight passed={approval.internal_resource_passed} label="자사 자원 활용" />
                  <TrafficLight passed={approval.cost_omission_passed} label="비용 누락" />
                </div>
                {approval.rule_logs && approval.rule_logs.length > 0 && (
                  <div className="space-y-2 border-t border-gray-200 pt-3 mt-3">
                    {approval.rule_logs.map((r: any, i: number) => (
                      <div key={i} className={clsx("p-2 rounded text-xs", r.passed ? "bg-white" : "bg-red-50")}>
                        <div className="flex items-center gap-1 font-medium mb-0.5">
                          {r.passed ? <CheckCircle size={12} className="text-success" /> : <XCircle size={12} className="text-danger" />}
                          {RULE_LABELS[r.rule_code] || r.rule_code}
                        </div>
                        <p className="text-gray-500">{r.message}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* AI 결재 실행 버튼 */}
            <button
              onClick={handleRunApproval}
              disabled={running}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              <Clock size={16} />
              {running ? "결재 처리 중..." : approval ? "재결재 실행" : "AI 결재 실행"}
            </button>

            {/* ── 인간 결재 ──────────────────────────────────── */}
            <div className="card">
              <p className="text-xs font-semibold text-gray-500 mb-3">담당자 결재</p>
              <HumanDecisionPanel
                sheet={sheet}
                onUpdated={(updated) => setSheet(updated)}
              />
            </div>

            {/* 파싱 경고 */}
            {sheet.notes && (
              <div className="card bg-yellow-50 border border-yellow-200">
                <p className="text-xs font-medium text-yellow-700 mb-1">⚠️ 파싱 경고</p>
                <p className="text-xs text-yellow-600">{sheet.notes}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
