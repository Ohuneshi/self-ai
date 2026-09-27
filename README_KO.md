# Self AI — 배포형 MVP

현재 Self AI 프로토타입의 핵심 5단계 인지 로직을 Python 백엔드에 유지하고, 캐릭터/UI를 반응형 JavaScript Canvas 웹앱으로 분리한 배포용 MVP입니다.

## 구조
- Python/WGSI: `app.py`, `brain.py`
- 웹 UI: `web/index.html`, `web/style.css`, `web/app.js`
- 기억: SQLite 호환 Turso Cloud (`turso_serverless`)
- AI: Gemini API (`GEMINI_API_KEY`)
- 사용자별 기억: `self_ai_user` 쿠키로 익명 분리

## 무료 배포 구성
GitHub는 소스 저장소, Render Free Web Service는 Python 백엔드와 정적 웹 제공, Turso는 SQLite 호환 영구 DB 역할을 맡습니다.

GitHub Pages는 Python 서버를 실행할 수 없으므로 전체 앱을 GitHub Pages 하나로 배포하지 않습니다.

## 배포 순서
1. GitHub 저장소에 이 프로젝트를 push합니다.
2. Turso Cloud에서 DB를 만든 뒤 `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`을 준비합니다.
3. Render에서 GitHub 저장소를 연결하고 Free Web Service로 생성합니다.
4. Render 환경변수에 `GEMINI_API_KEY`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`을 등록합니다.
5. Render가 제공하는 `onrender.com` 주소 하나만 공유하면 됩니다.

## 로컬 실행
```
pip install -r requirements.txt
set DEMO_MODE=1
python app.py
```

브라우저에서 `http://127.0.0.1:5000`을 엽니다.
