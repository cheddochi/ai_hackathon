# Contributing Guide

## 브랜치 전략

```
main        → 운영 (Railway 자동 배포)
develop     → 통합 개발
feature/*   → 기능 개발
fix/*       → 버그 수정
```

## 작업 흐름

```bash
git checkout develop
git pull origin develop
git checkout -b feature/my-feature

# 작업 후
git add .
git commit -m "feat: 기능 설명"
git push origin feature/my-feature

# GitHub에서 develop으로 PR 생성
```

## 커밋 메시지 규칙

| 타입 | 설명 |
|------|------|
| feat | 새 기능 |
| fix | 버그 수정 |
| docs | 문서 수정 (개발계획서 포함) |
| refactor | 리팩토링 |
| test | 테스트 |
| chore | 빌드/설정 변경 |

## 버전 업데이트 규칙

개발계획서.md 수정 시 **반드시** `frontend/src/config/version.ts`도 함께 수정하고 커밋합니다.

```bash
# 예시
git add 개발계획서.md frontend/src/config/version.ts
git commit -m "docs: v1.1.0 — GP룰 기준 업데이트"
```

## 로컬 개발 환경

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # 환경변수 설정
alembic upgrade head      # DB 마이그레이션
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

## 환경변수

### Backend (.env)
```
DATABASE_URL=postgresql://user:pass@host:5432/dbname
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```
