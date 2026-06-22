"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import Header from "@/components/layout/Header";
import { profitSheetApi } from "@/lib/api";
import { Plus, Upload, Search, CheckCircle2, XCircle, AlertCircle, X, Loader2 } from "lucide-react";
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

type BulkResult = {
  filename: string;
  hbl_no: string;
  sheet_id: number | null;
  status: "success" | "duplicate" | "error";
  warnings: string[];
};

function fmt(n: number | null) {
  if (n == null) return "—";
  return n.toLocaleString("ja-JP", { maximumFractionDigits: 0 });
}

// ── 드래그앤드롭 영역 ────────────────────────────────────────
function DropZone({
  onFiles,
  uploading,
}: {
  onFiles: (files: File[]) => void;
  uploading: boolean;
}) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const files = Array.from(e.dataTransfer.files).filter((f) =>
        f.name.toLowerCase().endsWith(".pdf")
      );
      if (files.length > 0) onFiles(files);
    },
    [onFiles]
  );

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !uploading && inputRef.current?.click()}
      className={clsx(
        "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all select-none",
        dragging
          ? "border-accent bg-accent/5 scale-[1.01]"
          : "border-gray-200 hover:border-accent/60 hover:bg-gray-50",
        uploading && "pointer-events-none opacity-60"
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        multiple
        className="hidden"
        onChange={(e) => {
          const files = Array.from(e.target.files || []);
          if (files.length > 0) onFiles(files);
          e.target.value = "";
        }}
      />
      {uploading ? (
        <div className="flex flex-col items-center gap-2 text-gray-500">
          <Loader2 size={32} className="animate-spin text-accent" />
          <p className="text-sm font-medium">파일 처리 중...</p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2 text-gray-400">
          <Upload size={32} className={clsx(dragging ? "text-accent" : "text-gray-300")} />
          <p className="text-sm font-medium text-gray-600">
            PDF 파일을 드래그하거나 클릭해서 선택
          </p>
          <p className="text-xs">복수 파일 동시 업로드 가능 · OCR 지원</p>
        </div>
      )}
    </div>
  );
}

// ── 업로드 결과 패널 ─────────────────────────────────────────
function ResultPanel({
  results,
  onClose,
}: {
  results: BulkResult[];
  onClose: () => void;
}) {
  const success = results.filter((r) => r.status === "success").length;
  const duplicate = results.filter((r) => r.status === "duplicate").length;
  const error = results.filter((r) => r.status === "error").length;

  return (
    <div className="card border border-gray-200 relative">
      <button
        onClick={onClose}
        className="absolute top-3 right-3 text-gray-400 hover:text-gray-600"
      >
        <X size={14} />
      </button>
      {/* 요약 */}
      <div className="flex gap-4 pb-3 border-b border-gray-100 mb-3">
        <span className="flex items-center gap-1 text-sm text-green-700 font-medium">
          <CheckCircle2 size={14} /> {success}건 성공
        </span>
        {duplicate > 0 && (
          <span className="flex items-center gap-1 text-sm text-yellow-700 font-medium">
            <AlertCircle size={14} /> {duplicate}건 중복
          </span>
        )}
        {error > 0 && (
          <span className="flex items-center gap-1 text-sm text-red-600 font-medium">
            <XCircle size={14} /> {error}건 실패
          </span>
        )}
      </div>
      {/* 파일별 상세 */}
      <ul className="space-y-1 max-h-48 overflow-y-auto text-sm">
        {results.map((r, i) => (
          <li key={i} className="flex items-start gap-2">
            {r.status === "success" && <CheckCircle2 size={14} className="text-green-600 mt-0.5 shrink-0" />}
            {r.status === "duplicate" && <AlertCircle size={14} className="text-yellow-600 mt-0.5 shrink-0" />}
            {r.status === "error" && <XCircle size={14} className="text-red-500 mt-0.5 shrink-0" />}
            <div className="min-w-0">
              <span className="font-medium text-gray-700 truncate">{r.filename}</span>
              {r.hbl_no && (
                <span className="ml-2 text-xs text-gray-400">H.B/L: {r.hbl_no}</span>
              )}
              {r.warnings.length > 0 && (
                <ul className="mt-0.5 space-y-0.5">
                  {r.warnings.map((w, j) => (
                    <li key={j} className="text-xs text-gray-500">⚠ {w}</li>
                  ))}
                </ul>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── 메인 페이지 ──────────────────────────────────────────────
export default function ProfitSheetListPage() {
  const [sheets, setSheets] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [uploading, setUploading] = useState(false);
  const [bulkResults, setBulkResults] = useState<BulkResult[] | null>(null);
  const [showDropZone, setShowDropZone] = useState(false);

  const load = () =>
    profitSheetApi
      .list(search ? { customer_name: search } : {})
      .then((r) => setSheets(r.data))
      .catch(() => {});

  useEffect(() => { load(); }, [search]);

  const handleFiles = async (files: File[]) => {
    setUploading(true);
    setBulkResults(null);
    try {
      if (files.length === 1 && !files[0].name.endsWith(".pdf")) {
        // Excel single
        await profitSheetApi.uploadExcel(files[0]);
        load();
      } else if (files.length === 1) {
        // Single PDF → 기존 단건 API
        const res = await profitSheetApi.uploadPdf(files[0]);
        setBulkResults([
          {
            filename: files[0].name,
            hbl_no: res.data.case_no || "",
            sheet_id: res.data.id,
            status: "success",
            warnings: [],
          },
        ]);
        load();
      } else {
        // Bulk PDF
        const res = await profitSheetApi.uploadPdfBulk(files);
        setBulkResults(res.data.results);
        load();
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "업로드 실패";
      setBulkResults([
        { filename: files.map((f) => f.name).join(", "), hbl_no: "", sheet_id: null, status: "error", warnings: [msg] },
      ]);
    } finally {
      setUploading(false);
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
            <button
              onClick={() => { setShowDropZone((v) => !v); setBulkResults(null); }}
              className={clsx(
                "btn-secondary flex items-center gap-2 text-sm",
                showDropZone && "bg-accent/10 border-accent/40"
              )}
            >
              <Upload size={14} />
              파일 업로드
            </button>
            <Link href="/profit-sheet/new" className="btn-primary flex items-center gap-2 text-sm">
              <Plus size={14} />
              새 안건 등록
            </Link>
          </div>
        </div>

        {/* 드래그앤드롭 영역 */}
        {showDropZone && (
          <div className="space-y-3">
            <DropZone onFiles={handleFiles} uploading={uploading} />
            {bulkResults && (
              <ResultPanel results={bulkResults} onClose={() => setBulkResults(null)} />
            )}
          </div>
        )}

        {/* 테이블 */}
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {["안건번호", "업무코드", "거래처", "담당자", "출발→도착", "매출(¥)", "GP(¥)", "GP율", "상태", "등록일"].map((h) => (
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
                  <td colSpan={10} className="px-4 py-12 text-center text-sm text-gray-400">
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
