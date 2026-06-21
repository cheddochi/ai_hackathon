"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import { profitSheetApi } from "@/lib/api";
import { Plus, Trash2 } from "lucide-react";

const JOB_CODES = ["SE", "SE+", "SE++", "SE+++", "SI", "SI+", "SI++", "SI+++",
  "AE", "AE+", "AE++", "AE+++", "AI", "AI+", "AI++", "AI+++", "PJT"];
const CUSTOMER_TYPES = ["SHIPPER", "FORWARDER", "PARTNER"];
const CURRENCIES = ["JPY", "USD", "KRW"];

const CHARGE_CODES = [
  "OF", "THC", "BAF", "WAF", "CIC", "EBS", "CRS", "EFS",
  "DOC", "BL", "DO", "SEAL", "AFR", "AMS", "ENS", "ISPS",
  "DUTY", "VAT", "FOOD", "QUARANTINE", "INSPECTION",
  "DRAYAGE", "HIGHWAY", "DELIVERY",
  "STORAGE", "DEVAN", "VANNING", "PICKING", "LABELING", "HANDLING",
  "AF", "FSC", "SSC", "AWB",
];

interface Detail {
  charge_code: string;
  is_revenue: boolean;
  currency: string;
  amount: string;
  partner_name: string;
}

export default function NewProfitSheetPage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    job_code: "SE",
    customer_name: "",
    customer_type: "SHIPPER",
    partner_name: "",
    origin_port: "",
    dest_port: "",
    weight_kg: "",
    cbm: "",
    container_type: "",
    exchange_rate_usd: "150",
    notes: "",
  });
  const [details, setDetails] = useState<Detail[]>([
    { charge_code: "OF", is_revenue: true, currency: "JPY", amount: "", partner_name: "" },
    { charge_code: "OF", is_revenue: false, currency: "JPY", amount: "", partner_name: "" },
  ]);

  const addDetail = (isRevenue: boolean) =>
    setDetails((d) => [...d, { charge_code: "THC", is_revenue: isRevenue, currency: "JPY", amount: "", partner_name: "" }]);

  const removeDetail = (i: number) => setDetails((d) => d.filter((_, j) => j !== i));

  const updateDetail = (i: number, key: keyof Detail, value: string | boolean) =>
    setDetails((d) => d.map((row, j) => (j === i ? { ...row, [key]: value } : row)));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        ...form,
        weight_kg: form.weight_kg ? parseFloat(form.weight_kg) : null,
        cbm: form.cbm ? parseFloat(form.cbm) : null,
        exchange_rate_usd: parseFloat(form.exchange_rate_usd),
        details: details
          .filter((d) => d.amount && parseFloat(d.amount) > 0)
          .map((d) => ({ ...d, amount: parseFloat(d.amount) })),
      };
      const res = await profitSheetApi.create(payload);
      router.push(`/approval/${res.data.id}`);
    } catch {
      alert("저장 실패");
    } finally {
      setSaving(false);
    }
  };

  const renderDetails = (isRevenue: boolean) => (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className={`text-xs font-semibold ${isRevenue ? "text-success" : "text-danger"}`}>
          {isRevenue ? "▲ 매출 항목" : "▼ 매입 항목"}
        </span>
        <button type="button" onClick={() => addDetail(isRevenue)}
          className="text-xs text-accent hover:text-indigo-700 flex items-center gap-1">
          <Plus size={12} /> 항목 추가
        </button>
      </div>
      {details.filter((d) => d.is_revenue === isRevenue).length === 0 && (
        <p className="text-xs text-gray-400 py-2">항목 없음</p>
      )}
      {details.map((d, i) =>
        d.is_revenue !== isRevenue ? null : (
          <div key={i} className="flex gap-2 items-center">
            <select value={d.charge_code} onChange={(e) => updateDetail(i, "charge_code", e.target.value)}
              className="border border-gray-300 rounded px-2 py-1.5 text-xs w-28">
              {CHARGE_CODES.map((c) => <option key={c}>{c}</option>)}
            </select>
            <select value={d.currency} onChange={(e) => updateDetail(i, "currency", e.target.value)}
              className="border border-gray-300 rounded px-2 py-1.5 text-xs w-16">
              {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
            </select>
            <input type="number" placeholder="금액" value={d.amount}
              onChange={(e) => updateDetail(i, "amount", e.target.value)}
              className="border border-gray-300 rounded px-2 py-1.5 text-xs w-28 text-right" />
            <input type="text" placeholder="파트너/업체명" value={d.partner_name}
              onChange={(e) => updateDetail(i, "partner_name", e.target.value)}
              className="border border-gray-300 rounded px-2 py-1.5 text-xs flex-1" />
            <button type="button" onClick={() => removeDetail(i)}
              className="text-gray-300 hover:text-danger transition-colors">
              <Trash2 size={14} />
            </button>
          </div>
        )
      )}
    </div>
  );

  return (
    <div>
      <Header title="새 안건 등록" />
      <div className="p-6 max-w-3xl">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* 기본 정보 */}
          <div className="card space-y-4">
            <h2 className="text-sm font-semibold text-gray-700">기본 정보</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">업무코드 *</label>
                <select value={form.job_code} onChange={(e) => setForm({ ...form, job_code: e.target.value })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm">
                  {JOB_CODES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">거래처 유형 *</label>
                <select value={form.customer_type} onChange={(e) => setForm({ ...form, customer_type: e.target.value })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm">
                  {CUSTOMER_TYPES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">거래처명</label>
                <input value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm" placeholder="예: ABC Corp" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">파트너명</label>
                <input value={form.partner_name} onChange={(e) => setForm({ ...form, partner_name: e.target.value })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm" placeholder="예: 태웅로직스" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">출발지 (PORT)</label>
                <input value={form.origin_port} onChange={(e) => setForm({ ...form, origin_port: e.target.value.toUpperCase() })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono" placeholder="TOKYO" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">도착지 (PORT)</label>
                <input value={form.dest_port} onChange={(e) => setForm({ ...form, dest_port: e.target.value.toUpperCase() })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono" placeholder="BUSAN" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">중량 (KG)</label>
                <input type="number" value={form.weight_kg} onChange={(e) => setForm({ ...form, weight_kg: e.target.value })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm" placeholder="1000" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">CBM</label>
                <input type="number" value={form.cbm} onChange={(e) => setForm({ ...form, cbm: e.target.value })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm" placeholder="2.5" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">컨테이너</label>
                <input value={form.container_type} onChange={(e) => setForm({ ...form, container_type: e.target.value.toUpperCase() })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono" placeholder="20GP / LCL" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">USD 환율 (→JPY)</label>
                <input type="number" value={form.exchange_rate_usd} onChange={(e) => setForm({ ...form, exchange_rate_usd: e.target.value })}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm" />
              </div>
            </div>
          </div>

          {/* 매출/매입 항목 */}
          <div className="card space-y-6">
            <h2 className="text-sm font-semibold text-gray-700">매출 / 매입 항목</h2>
            {renderDetails(true)}
            <hr className="border-gray-100" />
            {renderDetails(false)}
          </div>

          <div className="flex gap-3">
            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? "저장 중..." : "안건 저장 후 심사 진행"}
            </button>
            <button type="button" onClick={() => router.back()} className="btn-secondary">
              취소
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
