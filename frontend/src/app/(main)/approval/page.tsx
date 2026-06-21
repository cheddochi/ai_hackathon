"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/layout/Header";
import { profitSheetApi } from "@/lib/api";
import clsx from "clsx";

const STATUS_STYLE: Record<string, string> = {
  PENDING: "bg-gray-100 text-gray-600",
  APPROVED: "bg-green-100 text-green-700",
  CONDITIONAL: "bg-yellow-100 text-yellow-700",
  REVIEW: "bg-orange-100 text-orange-700",
  REJECTED: "bg-red-100 text-red-700",
};
const STATUS_LABEL: Record<string, string> = {
  PENDING: "심사 대기",
  APPROVED: "승인 가능",
  CONDITIONAL: "조건부 승인",
  REVIEW: "검토 필요",
  REJECTED: "부적합",
};

export default function ApprovalListPage() {
  const [sheets, setSheets] = useState<any[]>([]);
  const [filterStatus, setFilterStatus] = useState("PENDING");

  useEffect(() => {
    profitSheetApi.list(filterStatus ? { status: filterStatus } : {})
      .then((r) => setSheets(r.data))
      .catch(() => {});
  }, [filterStatus]);

  return (
    <div>
      <Header title="안건 심사" />
      <div className="p-6 space-y-4">
        {/* 필터 탭 */}
        <div className="flex gap-2 flex-wrap">
          {["", "PENDING", "APPROVED", "CONDITIONAL", "REVIEW", "REJECTED"].map((s) => (
            <button key={s} onClick={() => setFilterStatus(s)}
              className={clsx("badge px-3 py-1.5 text-sm cursor-pointer transition-colors",
                filterStatus === s ? "bg-accent text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
              {s ? STATUS_LABEL[s] : "전체"}
            </button>
          ))}
        </div>

        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {["안건번호", "업무코드", "거래처", "구분", "담당자", "매출(¥)", "GP(¥)", "GP율", "상태", "등록일"].map((h) => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sheets.map((s) => (
                <tr key={s.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <Link href={`/approval/${s.id}`} className="text-accent font-medium hover:underline">
                      {s.case_no || "—"}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{s.job_code}</td>
                  <td className="px-4 py-3">{s.customer_name || "—"}</td>
                  <td className="px-4 py-3"><span className="badge bg-gray-100 text-gray-500">{s.customer_type || "—"}</span></td>
                  <td className="px-4 py-3 text-gray-600">{s.assignee_name || "—"}</td>
                  <td className="px-4 py-3 text-right font-semibold">
                    {s.total_revenue_jpy != null ? `¥${s.total_revenue_jpy.toLocaleString()}` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold text-success">
                    {s.gp_jpy != null ? `¥${s.gp_jpy.toLocaleString()}` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">{s.gp_rate != null ? `${s.gp_rate.toFixed(1)}%` : "—"}</td>
                  <td className="px-4 py-3">
                    <span className={clsx("badge", STATUS_STYLE[s.status])}>{STATUS_LABEL[s.status] || s.status}</span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {new Date(s.created_at).toLocaleDateString("ko-KR")}
                  </td>
                </tr>
              ))}
              {sheets.length === 0 && (
                <tr><td colSpan={10} className="px-4 py-12 text-center text-sm text-gray-400">해당 안건 없음</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
