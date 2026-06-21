"use client";
import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { todoApi } from "@/lib/api";
import { CheckCircle, Clock, AlertCircle } from "lucide-react";
import clsx from "clsx";

const PRIORITY_STYLE: Record<string, string> = {
  HIGH: "bg-red-100 text-red-700",
  MEDIUM: "bg-yellow-100 text-yellow-700",
  LOW: "bg-gray-100 text-gray-600",
};
const PRIORITY_LABEL: Record<string, string> = { HIGH: "긴급", MEDIUM: "보통", LOW: "낮음" };

const STATUS_STYLE: Record<string, string> = {
  OPEN: "bg-orange-100 text-orange-700",
  IN_PROGRESS: "bg-blue-100 text-blue-700",
  DONE: "bg-green-100 text-green-700",
};
const STATUS_LABEL: Record<string, string> = { OPEN: "미처리", IN_PROGRESS: "진행 중", DONE: "완료" };

export default function TodoPage() {
  const [todos, setTodos] = useState<any[]>([]);
  const [filter, setFilter] = useState("OPEN");

  const load = () =>
    todoApi.list(filter ? { status: filter } : {})
      .then((r) => setTodos(r.data))
      .catch(() => {});

  useEffect(() => { load(); }, [filter]);

  const updateStatus = async (id: number, status: string) => {
    await todoApi.update(id, { status });
    load();
  };

  return (
    <div>
      <Header title="개선 To-Do" />
      <div className="p-6 space-y-4">
        {/* 필터 */}
        <div className="flex gap-2">
          {["", "OPEN", "IN_PROGRESS", "DONE"].map((s) => (
            <button key={s} onClick={() => setFilter(s)}
              className={clsx("badge px-3 py-1.5 text-sm cursor-pointer transition-colors",
                filter === s ? "bg-accent text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
              {s ? STATUS_LABEL[s] : "전체"}
            </button>
          ))}
        </div>

        <div className="space-y-3">
          {todos.map((todo) => (
            <div key={todo.id} className="card flex items-start gap-4">
              <div className={clsx("mt-0.5 p-1 rounded",
                todo.priority === "HIGH" ? "text-danger" : "text-warning")}>
                <AlertCircle size={16} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className={clsx("badge text-xs", PRIORITY_STYLE[todo.priority])}>
                    {PRIORITY_LABEL[todo.priority]}
                  </span>
                  <span className={clsx("badge text-xs", STATUS_STYLE[todo.status])}>
                    {STATUS_LABEL[todo.status]}
                  </span>
                  {todo.case_no && (
                    <span className="text-xs text-accent font-medium">{todo.case_no}</span>
                  )}
                  {todo.customer_name && (
                    <span className="text-xs text-gray-400">{todo.customer_name}</span>
                  )}
                </div>
                <p className="text-sm font-medium text-gray-800">{todo.title}</p>
                {todo.description && (
                  <p className="text-xs text-gray-500 mt-1">{todo.description}</p>
                )}
                <p className="text-xs text-gray-400 mt-2">
                  {new Date(todo.created_at).toLocaleDateString("ko-KR")}
                </p>
              </div>
              <div className="flex gap-2 shrink-0">
                {todo.status === "OPEN" && (
                  <button onClick={() => updateStatus(todo.id, "IN_PROGRESS")}
                    className="btn-secondary text-xs flex items-center gap-1">
                    <Clock size={12} /> 진행 중
                  </button>
                )}
                {todo.status !== "DONE" && (
                  <button onClick={() => updateStatus(todo.id, "DONE")}
                    className="btn-primary text-xs flex items-center gap-1">
                    <CheckCircle size={12} /> 완료
                  </button>
                )}
              </div>
            </div>
          ))}
          {todos.length === 0 && (
            <div className="card text-center py-12">
              <CheckCircle size={32} className="text-success mx-auto mb-2" />
              <p className="text-sm text-gray-400">처리할 항목이 없습니다</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
