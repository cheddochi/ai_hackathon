"use client";
import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { dashboardApi } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { TrendingUp, Package, Users, Award } from "lucide-react";

const GRADE_COLORS: Record<string, string> = {
  우수: "text-success",
  정상: "text-accent",
  관리: "text-warning",
  개선: "text-danger",
};

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  PENDING: { label: "심사 대기", color: "bg-gray-100 text-gray-600" },
  APPROVED: { label: "승인 가능", color: "bg-green-100 text-green-700" },
  CONDITIONAL: { label: "조건부 승인", color: "bg-yellow-100 text-yellow-700" },
  REVIEW: { label: "검토 필요", color: "bg-orange-100 text-orange-700" },
  REJECTED: { label: "부적합", color: "bg-red-100 text-red-700" },
};

function fmt(n: number) {
  return n.toLocaleString("ja-JP", { maximumFractionDigits: 0 });
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<any>(null);
  const [customers, setCustomers] = useState<any[]>([]);
  const [productivity, setProductivity] = useState<any[]>([]);
  const [jobCodes, setJobCodes] = useState<any[]>([]);

  useEffect(() => {
    dashboardApi.summary().then((r) => setSummary(r.data));
    dashboardApi.topCustomers(10).then((r) => setCustomers(r.data));
    dashboardApi.productivity().then((r) => setProductivity(r.data));
    dashboardApi.gpByJobCode().then((r) => setJobCodes(r.data));
  }, []);

  return (
    <div>
      <Header title="대시보드" />
      <div className="p-6 space-y-6">
        {/* KPI 카드 */}
        <div className="grid grid-cols-4 gap-4">
          {[
            {
              label: "오늘 매출",
              value: summary ? `¥${fmt(summary.today.revenue_jpy)}` : "—",
              sub: `${summary?.today.count ?? 0}건`,
              icon: TrendingUp,
              color: "text-accent",
            },
            {
              label: "오늘 GP",
              value: summary ? `¥${fmt(summary.today.gp_jpy)}` : "—",
              sub: "",
              icon: Package,
              color: "text-success",
            },
            {
              label: "월간 GP",
              value: summary ? `¥${fmt(summary.monthly.gp_jpy)}` : "—",
              sub: summary ? `GP율 ${summary.monthly.gp_rate.toFixed(1)}%` : "",
              icon: Award,
              color: "text-accent",
            },
            {
              label: "연간 매출",
              value: summary ? `¥${fmt(summary.yearly.revenue_jpy)}` : "—",
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

        {/* 상태 현황 */}
        {summary && (
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">안건 상태 현황</h2>
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
        )}

        <div className="grid grid-cols-2 gap-6">
          {/* 거래처 TOP10 */}
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">거래처 TOP10 GP</h2>
            <div className="space-y-2">
              {customers.slice(0, 10).map((c, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400 w-4">{i + 1}</span>
                    <span className="text-gray-800 truncate max-w-32">{c.customer_name || "—"}</span>
                    <span className="badge bg-gray-100 text-gray-500">{c.customer_type}</span>
                  </div>
                  <div className="text-right">
                    <span className="font-semibold text-gray-900">¥{fmt(c.gp_jpy)}</span>
                    <span className="text-xs text-gray-400 ml-2">{c.gp_rate.toFixed(1)}%</span>
                  </div>
                </div>
              ))}
              {customers.length === 0 && (
                <p className="text-sm text-gray-400 text-center py-4">데이터 없음</p>
              )}
            </div>
          </div>

          {/* 생산성 현황 */}
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">직원별 생산성 (이번 달)</h2>
            <div className="space-y-2">
              {productivity.map((p, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-800">{p.user_name}</span>
                    <span className="text-xs text-gray-400">{p.department}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-20 bg-gray-100 rounded-full h-1.5">
                      <div
                        className="bg-accent h-1.5 rounded-full"
                        style={{ width: `${Math.min((p.total_point / 120) * 100, 100)}%` }}
                      />
                    </div>
                    <span className="font-semibold text-gray-900 w-10 text-right">
                      {p.total_point.toFixed(1)}P
                    </span>
                    <span className={`text-xs font-medium ${GRADE_COLORS[p.grade] || ""}`}>
                      {p.grade}
                    </span>
                  </div>
                </div>
              ))}
              {productivity.length === 0 && (
                <p className="text-sm text-gray-400 text-center py-4">데이터 없음</p>
              )}
            </div>
          </div>
        </div>

        {/* 업무코드별 GP 차트 */}
        {jobCodes.length > 0 && (
          <div className="card">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">업무코드별 GP 현황</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={jobCodes} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                <XAxis dataKey="job_code" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(v: number) => [`¥${fmt(v)}`, "GP"]}
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
      </div>
    </div>
  );
}
