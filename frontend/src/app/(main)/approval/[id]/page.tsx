"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import { profitSheetApi, approvalApi } from "@/lib/api";
import { CheckCircle, XCircle, AlertCircle, Clock, ChevronLeft } from "lucide-react";
import clsx from "clsx";

const JUDGMENT_CONFIG: Record<string, { label: string; color: string; bg: string; icon: typeof CheckCircle }> = {
  APPROVED:    { label: "승인 가능",    color: "text-success", bg: "bg-green-50 border-success",  icon: CheckCircle },
  CONDITIONAL: { label: "조건부 승인",  color: "text-warning", bg: "bg-yellow-50 border-warning", icon: AlertCircle },
  REVIEW:      { label: "검토 필요",    color: "text-orange-500", bg: "bg-orange-50 border-orange-400", icon: AlertCircle },
  REJECTED:    { label: "부적합",       color: "text-danger",  bg: "bg-red-50 border-danger",     icon: XCircle },
};

const RULE_LABELS: Record<string, string> = {
  GP_CHECK: "GP 기준 검증",
  PARTNER_FEE: "Partner Fee 검증",
  INTERNAL_RESOURCE: "자사 자원 활용",
  COST_OMISSION: "비용 누락 검증",
};

function TrafficLight({ passed, label }: { passed: boolean | null; label: string }) {
  if (passed === null) return null;
  return (
    <div className="flex items-center gap-2">
      <div className={clsx("w-3 h-3 rounded-full", passed ? "bg-success" : "bg-danger")} />
      <span className="text-xs text-gray-600">{label}</span>
    </div>
  );
}

export default function ApprovalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [sheet, setSheet] = useState<any>(null);
  const [approval, setApproval] = useState<any>(null);
  const [running, setRunning] = useState(false);

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

  if (!sheet) return <div className="p-6 text-sm text-gray-400">로딩 중...</div>;

  const cfg = approval ? JUDGMENT_CONFIG[approval.judgment] : null;

  return (
    <div>
      <Header title={`안건 심사 — ${sheet.case_no || `#${id}`}`} />
      <div className="p-6 space-y-6 max-w-5xl">
        {/* 뒤로 */}
        <button onClick={() => router.back()} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
          <ChevronLeft size={16} /> 목록으로
        </button>

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
                  ["USD 환율", sheet.exchange_rate_usd ? `${sheet.exchange_rate_usd}` : "—"],
                ].map(([label, value]) => (
                  <div key={label}>
                    <p className="text-xs text-gray-400">{label}</p>
                    <p className="font-medium text-gray-800">{value || "—"}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* GP 요약 */}
            <div className="card">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">수익성 요약</h2>
              <div className="grid grid-cols-3 gap-4">
                {[
                  { label: "총 매출", value: sheet.total_revenue_jpy, color: "text-gray-900" },
                  { label: "총 매입", value: sheet.total_cost_jpy, color: "text-danger" },
                  { label: "GP", value: sheet.gp_jpy, color: "text-success" },
                ].map((item) => (
                  <div key={item.label} className="text-center p-4 bg-gray-50 rounded-lg">
                    <p className="text-xs text-gray-400 mb-1">{item.label}</p>
                    <p className={clsx("text-lg font-semibold", item.color)}>
                      ¥{item.value?.toLocaleString() ?? "—"}
                    </p>
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

            {/* 매출/매입 상세 */}
            <div className="card">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">매출 / 매입 항목</h2>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left py-2 text-gray-400">구분</th>
                    <th className="text-left py-2 text-gray-400">코드</th>
                    <th className="text-left py-2 text-gray-400">항목명</th>
                    <th className="text-left py-2 text-gray-400">파트너</th>
                    <th className="text-right py-2 text-gray-400">금액</th>
                    <th className="text-right py-2 text-gray-400">엔 환산</th>
                  </tr>
                </thead>
                <tbody>
                  {(sheet.details || []).map((d: any, i: number) => (
                    <tr key={i} className={clsx("border-b border-gray-50", d.is_missing_flag && "bg-yellow-50")}>
                      <td className="py-2">
                        <span className={clsx("badge text-xs", d.is_revenue ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600")}>
                          {d.is_revenue ? "매출" : "매입"}
                        </span>
                      </td>
                      <td className="py-2 font-mono font-medium">{d.charge_code}</td>
                      <td className="py-2 text-gray-600">{d.charge_name || "—"}</td>
                      <td className="py-2 text-gray-500">{d.partner_name || "—"}</td>
                      <td className="py-2 text-right">{d.amount?.toLocaleString()} {d.currency}</td>
                      <td className="py-2 text-right font-medium">¥{d.amount_jpy?.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 우: 결재 패널 */}
          <div className="space-y-4">
            {/* 결재 결과 */}
            {cfg && (
              <div className={clsx("card border-2", cfg.bg)}>
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
                {/* 룰 상세 */}
                {approval.rule_logs && approval.rule_logs.length > 0 && (
                  <div className="space-y-2 border-t border-gray-200 pt-3 mt-3">
                    {approval.rule_logs.map((r: any, i: number) => (
                      <div key={i} className={clsx("p-2 rounded text-xs", r.passed ? "bg-white" : "bg-red-50")}>
                        <div className="flex items-center gap-1 font-medium mb-0.5">
                          {r.passed ? (
                            <CheckCircle size={12} className="text-success" />
                          ) : (
                            <XCircle size={12} className="text-danger" />
                          )}
                          {RULE_LABELS[r.rule_code] || r.rule_code}
                        </div>
                        <p className="text-gray-500">{r.message}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 결재 실행 버튼 */}
            <button
              onClick={handleRunApproval}
              disabled={running}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              <Clock size={16} />
              {running ? "결재 처리 중..." : approval ? "재결재 실행" : "AI 결재 실행"}
            </button>

            {/* 비고 */}
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
