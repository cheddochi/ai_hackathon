"use client";
import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import Header from "@/components/layout/Header";
import { profitSheetApi } from "@/lib/api";
import { Plus, Upload, Search } from "lucide-react";
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

function fmt(n: number | null) {
  if (n == null) return "—";
  return n.toLocaleString("ja-JP", { maximumFractionDigits: 0 });
}

export default function ProfitSheetListPage() {
  const [sheets, setSheets] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = () =>
    profitSheetApi
      .list(search ? { customer_name: search } : {})
      .then((r) => setSheets(r.data))
      .catch(() => {});

  useEffect(() => { load(); }, [search]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      if (file.name.endsWith(".pdf")) await profitSheetApi.uploadPdf(file);
      else await profitSheetApi.uploadExcel(file);
      load();
    } catch {
      alert("업로드 실패. 파일 형식을 확인해주세요.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div>
      <Header title="Profit Sheet" />
      <div className="p-6 space-y-4">
        {/* 액션 바 */}
        <div className="flex items-center justify-between gap-4">
          <div className="relative flex-1 max-w-xs">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="거래처명 검색"
              className="pl-8 pr-3 py-2 text-sm border border-gray-300 rounded w-full focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
          <div className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.xlsx,.xls"
              className="hidden"
              onChange={handleFileUpload}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <Upload size={14} />
              {uploading ? "업로드 중..." : "파일 업로드"}
            </button>
            <Link href="/profit-sheet/new" className="btn-primary flex items-center gap-2 text-sm">
              <Plus size={14} />
              새 안건 등록
            </Link>
          </div>
        </div>

        {/* 테이블 */}
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {["안건번호", "업무코드", "거래처", "구분", "담당자", "출발→도착", "매출(¥)", "GP(¥)", "GP율", "상태", "등록일"].map((h) => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sheets.map((s) => (
                <tr
                  key={s.id}
                  className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => (window.location.href = `/approval/${s.id}`)}
                >
                  <td className="px-4 py-3 font-medium text-accent">{s.case_no || "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs bg-gray-50 text-gray-700">{s.job_code}</td>
                  <td className="px-4 py-3">{s.customer_name || "—"}</td>
                  <td className="px-4 py-3">
                    <span className="badge bg-gray-100 text-gray-500">{s.customer_type || "—"}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{s.assignee_name || "—"}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {s.origin_port || "—"} → {s.dest_port || "—"}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold">{fmt(s.total_revenue_jpy)}</td>
                  <td className="px-4 py-3 text-right font-semibold text-success">{fmt(s.gp_jpy)}</td>
                  <td className="px-4 py-3 text-right">
                    {s.gp_rate != null ? `${s.gp_rate.toFixed(1)}%` : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span className={clsx("badge", STATUS_STYLE[s.status])}>
                      {STATUS_LABEL[s.status] || s.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {new Date(s.created_at).toLocaleDateString("ko-KR")}
                  </td>
                </tr>
              ))}
              {sheets.length === 0 && (
                <tr>
                  <td colSpan={11} className="px-4 py-12 text-center text-sm text-gray-400">
                    등록된 안건이 없습니다
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
