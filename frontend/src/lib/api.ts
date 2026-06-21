import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: { "Content-Type": "application/json" },
});

// 요청 인터셉터: JWT 토큰 자동 삽입
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 응답 인터셉터: 401 시 로그인 페이지로
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// ── Auth ───────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", new URLSearchParams({ username: email, password }), {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    }),
  me: () => api.get("/auth/me"),
};

// ── Profit Sheet ───────────────────────────────────────────
export const profitSheetApi = {
  list: (params?: Record<string, string | number>) => api.get("/profit-sheets", { params }),
  get: (id: number) => api.get(`/profit-sheets/${id}`),
  create: (data: unknown) => api.post("/profit-sheets", data),
  uploadPdf: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/profit-sheets/upload/pdf", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  uploadExcel: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/profit-sheets/upload/excel", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
};

// ── Approval ───────────────────────────────────────────────
export const approvalApi = {
  run: (sheetId: number) => api.post(`/approvals/${sheetId}/run`),
  history: (sheetId: number) => api.get(`/approvals/${sheetId}/history`),
};

// ── Dashboard ──────────────────────────────────────────────
export const dashboardApi = {
  summary: () => api.get("/dashboard/summary"),
  topCustomers: (limit = 10) => api.get("/dashboard/top-customers", { params: { limit } }),
  productivity: (yearMonth?: string) =>
    api.get("/dashboard/productivity", { params: yearMonth ? { year_month: yearMonth } : {} }),
  gpByJobCode: () => api.get("/dashboard/gp-by-job-code"),
};

// ── Todo ───────────────────────────────────────────────────
export const todoApi = {
  list: (params?: Record<string, string>) => api.get("/todos", { params }),
  update: (id: number, data: unknown) => api.patch(`/todos/${id}`, data),
};

// ── Master ─────────────────────────────────────────────────
export const masterApi = {
  customers: () => api.get("/master/customers"),
  createCustomer: (data: unknown) => api.post("/master/customers", data),
  partners: () => api.get("/master/partners"),
  createPartner: (data: unknown) => api.post("/master/partners", data),
  gpRules: () => api.get("/master/gp-rules"),
  createGpRule: (data: unknown) => api.post("/master/gp-rules", data),
  updateGpRule: (id: number, data: unknown) => api.patch(`/master/gp-rules/${id}`, data),
  exchangeRates: () => api.get("/master/exchange-rates"),
  createExchangeRate: (data: unknown) => api.post("/master/exchange-rates", data),
  jobCodes: () => api.get("/master/job-codes"),
};
