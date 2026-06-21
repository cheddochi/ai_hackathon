"use client";
import { APP_VERSION } from "@/config/version";
import { Bell } from "lucide-react";

interface HeaderProps {
  title: string;
}

export default function Header({ title }: HeaderProps) {
  return (
    <header className="h-14 bg-white border-b border-gray-100 flex items-center justify-between px-6">
      <h1 className="text-base font-semibold text-gray-900">{title}</h1>
      <div className="flex items-center gap-4">
        <button className="text-gray-400 hover:text-gray-600 transition-colors">
          <Bell size={18} />
        </button>
        {/* 버전 배지 — 개발계획서.md와 동기화 */}
        <span className="badge bg-gray-100 text-gray-500 text-xs">{APP_VERSION}</span>
      </div>
    </header>
  );
}
