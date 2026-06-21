"use client";
import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { masterApi } from "@/lib/api";
import { APP_VERSION } from "@/config/version";
import { Plus, RefreshCw } from "lucide-react";

const TAB_LIST = ["GP 기준", "환율", "거래처", "파트너", "업무코드"] as const;
type Tab = (typeof TAB_LIST)[number];

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("GP 기준");
  const [gpRules, setGpRules] = useState<any[]>([]);
  const [exchangeRates, setExchangeRates] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [partners, setPartners] = useState<any[]>([]);
  const [jobCodes, setJobCodes] = useState<any[]>([]);

  useEffect(() => {
    masterApi.gpRules().then((r) => setGpRules(r.data)).catch(() => {});
    masterApi.exchangeRates().then((r) => setExchangeRates(r.data)).catch(() => {});
    masterApi.customers().then((r) => setCustomers(r.data)).catch(() => {});
    masterApi.partners().then((r) => setPartners(r.data)).catch(() => {});
    masterApi.jobCodes().then((r) => setJobCodes(r.data)).catch(() => {});
  }, []);

  return (
    <div>
      <Header title="관리자 설정" />
      <div className="p-6 space-y-6">
        {/* 탭 */}
        <div className="flex gap-1 border-b border-gray-200">
          {TAB_LIST.map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                tab === t ? "border-accent text-accent" : "border-transparent text-gray-500 hover:text-gray-700"
              }`}>
              {t}
            </button>
          ))}
        </div>

        {/* GP 기준 */}
        {tab === "GP 기준" && (
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <p className="text-xs text-gray-500">AI 결재 시 적용되는 GP 기준입니다. 변경 시 신규 결재부터 적용됩니다.</p>
            </div>
            <div className="card p-0 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    {["기준명", "유형", "업무코드", "거래처구분", "최소GP(¥)", "최소GP율(%)"].map((h) => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {gpRules.map((r) => (
                    <tr key={r.id} className="border-t border-gray-50">
                      <td className="px-4 py-3 font-medium">{r.rule_name}</td>
                      <td className="px-4 py-3 text-xs"><span className="badge bg-accent-light text-accent">{r.rule_type}</span></td>
                      <td className="px-4 py-3 font-mono text-xs">{r.job_code || "전체"}</td>
                      <td className="px-4 py-3">{r.customer_type || "전체"}</td>
                      <td className="px-4 py-3 text-right">{r.min_gp_jpy?.toLocaleString() ?? "—"}</td>
                      <td className="px-4 py-3 text-right">{r.min_gp_rate != null ? `${r.min_gp_rate}%` : "—"}</td>
                    </tr>
                  ))}
                  {gpRules.length === 0 && (
                    <tr><td colSpan={6} className="px-4 py-8 text-center text-sm text-gray-400">GP 기준 없음</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 환율 */}
        {tab === "환율" && (
          <div className="card p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {["통화", "대상", "환율", "기준일"].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {exchangeRates.map((r) => (
                  <tr key={r.id} className="border-t border-gray-50">
                    <td className="px-4 py-3 font-mono font-medium">{r.from_currency}</td>
                    <td className="px-4 py-3 font-mono">{r.to_currency}</td>
                    <td className="px-4 py-3 text-right font-semibold">{r.rate.toLocaleString()}</td>
                    <td className="px-4 py-3 text-xs text-gray-400">{new Date(r.effective_date).toLocaleDateString("ko-KR")}</td>
                  </tr>
                ))}
                {exchangeRates.length === 0 && (
                  <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-gray-400">환율 없음</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* 거래처 */}
        {tab === "거래처" && (
          <div className="card p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {["코드", "거래처명", "구분", "국가", "연락처"].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {customers.map((c) => (
                  <tr key={c.id} className="border-t border-gray-50">
                    <td className="px-4 py-3 font-mono text-xs">{c.code}</td>
                    <td className="px-4 py-3 font-medium">{c.name}</td>
                    <td className="px-4 py-3"><span className="badge bg-gray-100 text-gray-600">{c.customer_type}</span></td>
                    <td className="px-4 py-3 text-gray-500">{c.country || "—"}</td>
                    <td className="px-4 py-3 text-gray-500">{c.contact || "—"}</td>
                  </tr>
                ))}
                {customers.length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">거래처 없음</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* 파트너 */}
        {tab === "파트너" && (
          <div className="card p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {["코드", "파트너명", "유형", "국가", "최대Fee(¥)", "최대Fee율"].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {partners.map((p) => (
                  <tr key={p.id} className="border-t border-gray-50">
                    <td className="px-4 py-3 font-mono text-xs">{p.code}</td>
                    <td className="px-4 py-3 font-medium">{p.name}</td>
                    <td className="px-4 py-3 text-gray-500">{p.partner_type || "—"}</td>
                    <td className="px-4 py-3 text-gray-500">{p.country || "—"}</td>
                    <td className="px-4 py-3 text-right">{p.max_fee_per_case?.toLocaleString() ?? "—"}</td>
                    <td className="px-4 py-3 text-right">{p.max_fee_rate != null ? `${p.max_fee_rate}%` : "—"}</td>
                  </tr>
                ))}
                {partners.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-sm text-gray-400">파트너 없음</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* 업무코드 */}
        {tab === "업무코드" && (
          <div className="card p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {["코드", "설명", "운송유형", "통관", "운송", "창고", "POINT"].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {jobCodes.map((j) => (
                  <tr key={j.id} className="border-t border-gray-50">
                    <td className="px-4 py-3 font-mono font-semibold text-accent">{j.code}</td>
                    <td className="px-4 py-3">{j.description}</td>
                    <td className="px-4 py-3 text-gray-500">{j.transport_type || "—"}</td>
                    <td className="px-4 py-3 text-center">{j.includes_customs ? "✓" : "—"}</td>
                    <td className="px-4 py-3 text-center">{j.includes_transport ? "✓" : "—"}</td>
                    <td className="px-4 py-3 text-center">{j.includes_warehouse ? "✓" : "—"}</td>
                    <td className="px-4 py-3 text-right font-semibold">{j.point}</td>
                  </tr>
                ))}
                {jobCodes.length === 0 && (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-400">업무코드 없음</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* 버전 정보 */}
        <div className="card bg-gray-50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-gray-600">시스템 버전</p>
              <p className="text-lg font-bold text-accent mt-1">{APP_VERSION}</p>
              <p className="text-xs text-gray-400 mt-1">개발계획서.md와 동기화됩니다</p>
            </div>
            <div className="text-gray-300">
              <RefreshCw size={24} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
