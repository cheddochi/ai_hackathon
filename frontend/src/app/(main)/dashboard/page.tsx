"use client";
import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { dashboardApi } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { TrendingUp, Package, Users, Award, ThumbsUp, ThumbsDown } from "lucide-react";

const GRADE_COLORS: Record<string, string> = {
  우수: "text-success",
  정상: "text-accent",
  관리: "text-warning",
  개선: "text-danger",
};

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  PENDING:     { label: "심사 대기",   color: "bg-gray-100 text-gray-600" },
  APPROVED:    { label: "승인 가능",   color: "bg-green-100 text-green-700" },
  CONDITIONAL: { label: "조건부 승인", color: "bg-yellow-100 text-yellow-700" },
  REVIEW:      { label: "검토 필요",   color: "bg-orange-100 text-orange-700" },
  REJECTED:    { label: "부적합",      color: "bg-red-100 text-red-700" },
};

// 기본 환율 (JPY → KRW) — 실시간 환율이 없을 때 사용
const DEFAULT_KRW_PER_JPY = 9.5;

function fmtKrw(jpy: number, rate = DEFAULT_KRW_PER_JPY) {
  const krw = Math.round(jpy * rate);
  if (krw >= 100_000_000) return `₩${(krw / 100_000_000).toFixed(1)}억`;
  if (krw >= 10_000)      return `₩${(krw / 10_000).toFixed(0)}만`;
  return `₩${krw.toLocaleString("ko-KR")}`;
}
function fmtKrwFull(jpy: number, rate = DEFAULT_KRW_PER_JPY) {
  return `₩${Math.round(jpy * rate).toLocaleString("ko-KR")}`;
}

export default function DashboardPage() {
  const [summary, setSummary]         = useState<any>(null);
  const [customers, setCustomers]     = useState<any[]>([]);
  const [productivity, setProductivity] = useState<any[]>([]);
  const [jobCodes, setJobCodes]       = useState<any[]>([]);
  const [loading, setLoading]         = useState(true);

  useEffect(() => {
    Promise.all([
      dashboardApi.summary().then((r) => setSummary(r.data)),
      dashboardApi.topCustomers(10).then((r) => setCustomers(r.data)),
      dashboardApi.productivity().then((r) => setProductivity(r.data)),
      dashboardApi.gpByJobCode().then((r) => setJobCodes(r.data)),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div>
        <Header title="대시보드" />
        <div className="p-6 flex items-center justify-center h-64 text-sm text-gray-400">
          데이터 불러오는 중...
        </div>
      </div>
    );
  }

  const totalCount = Object.values(summary?.status_counts || {}).reduce((a: number, b: any) => a + b, 0);

  return (
    <div>
      <Header title="대시보드" />
      <div className="p-6 space-y-6">

        {/* ── KPI 카드 ── */}
        <div className="grid grid-cols-4 gap-4">
          {[
            {
              label: "오늘 매출",
              value: summary ? fmtKrw(summary.today.revenue_jpy) : "—",
              sub: `${summary?.today.count ?? 0}건`,
              icon: TrendingUp,
              color: "text-accent",
            },
            {
              label: "오늘 GP",
              value: summary ? fmtKrw(summary.today.gp_jpy) : "—",
              sub: summary?.today.count > 0
                ? `GP율 ${summary.today.revenue_jpy > 0 ? (summary.today.gp_jpy / summary.today.revenue_jpy * 100).toFixed(1) : 0}%`
                : "",
              icon: Package,
              color: "text-success",
            },
            {
              label: "월간 GP",
              value: summary ? fmtKrw(summary.monthly.gp_jpy) : "—",
              sub: summary ? `GP율 ${summary.monthly.gp_rate.toFixed(1)}%` : "",
              icon: Award,
              color: "text-accent",
            },
            {
              label: "연간 매출",
              value: summary ? fmtKrw(summary.yearly.revenue_jpy) : "—",
              sub: `${summary?.yearly.count ?? 0}건`,
              icon: Users,
              color: "text-gray-600",
            },
          ].map((kpi) => (
            <div key={kpi.label} className="card flex items-start gap-4">
              <div className={`mt-0.5 ${kpi.color}`}>
                <kpi.icon size={20} />
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">{kpi.label}</p>
                <p className="text-xl font-semibold text-gray-900">{kpi.value}</p>
                {kpi.sub && <p className="text-xs text-gray-400 mt-0.5">{kpi.sub}</p>}
              </div>
            </div>
          ))}
        </div>

        {/* ── 상태 현황 + 인간 결재 ── */}
        {summary && (
          <div className="card">
            <div className="flex items-start justify-between gap-6 flex-wrap">
              <div>
                <h2 className="text-sm font-semibold text-gray-700 mb-3">
                  AI 심사 상태 현황
                  <span className="ml-2 text-xs font-normal text-gray-400">전체 {totalCount}건</span>
                </h2>
                <div className="flex gap-3 flex-wrap">
                  {Object.entries(summary.status_counts || {}).map(([status, count]) => {
                    const s = STATUS_LABELS[status] || { label: status, color: "bg-gray-100 text-gray-600" };
                    return (
                      <div key={status} className={`badge ${s.color} px-3 py-1.5 text-sm`}>
                        {s.label} <span className="font-bold ml-1">{String(count)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div className="border-l border-gray-100 pl-6">
                <h2 className="text-sm font-semibold text-gray-700 mb-3">담당자 결재 현황</h2>
                <div className="flex gap-4">
                  <div className="flex items-center gap-2">
                    <ThumbsUp size={16} className="text-green-600" />
                    <span className="text-sm text-gray-600">승인</span>
                    <span className="text-lg font-bold text-green-600">
                      {summary.human_decision?.approved ?? 0}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <ThumbsDown size={16} className="text-red-500" />
                    <span className="text-sm text-gray-600">반려</span>
                    <span className="text-lg font-bold text-red-500">
                      {summary.human_decision?.rejected ?? 0}
                    </span>
                  </div>
                  <div className="text-sm text-gray-400 self-center">
                    미결 {totalCount - (summary.human_decision?.approved ?? 0) - (summary.human_decision?.rejected ?? 0)}건
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── 거래처 TOP10 + 직원 생산성 ── */}
        <div className="grid grid-cols-2 gap-6">
          {/* 거래처 TOP10 */}
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">거래처 TOP10 GP</h2>
            <div className="space-y-2">
              {customers.slice(0, 10).map((c, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs text-gray-400 w-4 shrink-0">{i + 1}</span>
                    <span className="text-gray-800 truncate max-w-36">{c.customer_name || "—"}</span>
                    {c.customer_type && (
                      <span className="badge bg-gray-100 text-gray-500 shrink-0 text-xs">{c.customer_type}</span>
                    )}
                  </div>
                  <div className="text-right shrink-0 ml-2">
                    <span className="font-semibold text-gray-900">
                      {fmtKrwFull(c.gp_jpy)}
                    </span>
                    <span className="text-xs text-gray-400 ml-1">{c.gp_rate.toFixed(1)}%</span>
                  </div>
                </div>
              ))}
              {customers.length === 0 && (
                <p className="text-sm text-gray-400 text-center py-6">데이터 없음</p>
              )}
            </div>
          </div>

          {/* 직원 생산성 */}
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">
              직원별 생산성 (이번 달)
              <span className="ml-2 text-xs font-normal text-gray-400">등록 건수 기준</span>
            </h2>
            <div className="space-y-3">
              {productivity.map((p, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-800 font-medium">{p.user_name}</span>
                    {p.department && (
                      <span className="text-xs text-gray-400">{p.department}</span>
                    )}
                    <span className="text-xs text-gray-400">{p.case_count}건</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-20 bg-gray-100 rounded-full h-1.5">
                      <div
                        className="bg-accent h-1.5 rounded-full"
                        style={{ width: `${Math.min((p.total_point / 20) * 100, 100)}%` }}
                      />
                    </div>
                    <span className="font-semibold text-gray-900 w-12 text-right">
                      {p.total_point.toFixed(1)}P
                    </span>
                    <span className={`text-xs font-medium w-8 ${GRADE_COLORS[p.grade] || ""}`}>
                      {p.grade}
                    </span>
                  </div>
                </div>
              ))}
              {productivity.length === 0 && (
                <p className="text-sm text-gray-400 text-center py-6">이번 달 등록 건 없음</p>
              )}
            </div>
          </div>
        </div>

        {/* ── 업무코드별 GP 차트 ── */}
        {jobCodes.length > 0 && (
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">업무코드별 GP 현황 (₩)</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={jobCodes} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                <XAxis dataKey="job_code" tick={{ fontSize: 12 }} />
                <YAxis
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => {
                    const krw = v * DEFAULT_KRW_PER_JPY;
                    return krw >= 10000 ? `${(krw / 10000).toFixed(0)}만` : `${krw}`;
                  }}
                />
                <Tooltip
                  formatter={(v: number) => [fmtKrwFull(v), "GP"]}
                  labelStyle={{ fontSize: 12 }}
                />
                <Bar dataKey="gp_jpy" radius={[4, 4, 0, 0]}>
                  {jobCodes.map((_, i) => (
                    <Cell key={i} fill="#4F46E5" />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        <p className="text-xs text-gray-400 text-right">
          * 금액은 원화(₩) 표시 · JPY→KRW 환율 {DEFAULT_KRW_PER_JPY} 적용 (각 계약 저장 환율 우선)
        </p>
      </div>
    </div>
  );
}
