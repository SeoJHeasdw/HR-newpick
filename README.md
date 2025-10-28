# AI 뉴스레터 자동 요약 및 발송 시스템

## 프로젝트 개요
Gmail로 수신되는 TLDR AI 뉴스레터를 자동으로 파싱하고, Azure OpenAI로 요약한 뒤, SMTP로 회사 메일 계정에 자동 발송하는 시스템입니다.

## 프로젝트 구조
```
newpick/
├── main.py              # 메인 워크플로우
├── config.example.py    # 설정 템플릿
├── config.py           # 실제 설정 파일 (별도 생성 필요)
├── requirements.txt     # 의존성 패키지
├── README.md           # 이 파일
└── logs/               # 로그 파일 디렉토리
```

## 설치 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 설정 파일 생성
`config.example.py`를 복사하여 `config.py`를 생성하고 필요한 정보를 입력하세요:

```bash
cp config.example.py config.py
```

### 3. config.py 설정

#### Gmail 앱 비밀번호 생성
1. Gmail 계정 설정으로 이동
2. 2단계 인증 활성화
3. 앱 비밀번호 생성: [Google 계정 관리](https://myaccount.google.com/apppasswords)
4. 생성된 16자리 비밀번호를 `GMAIL_APP_PASSWORD`에 입력

#### 필수 설정값
```python
# Gmail IMAP 설정
GMAIL_EMAIL = "your_email@gmail.com"
GMAIL_APP_PASSWORD = "16자리_앱_비밀번호"

# 받는 사람 설정
RECIPIENT_EMAIL = "your_company_email@company.com"

# TLDR 발신자 설정
TLDR_SENDER_EMAIL = "team@tldr.tech"
```

## 사용 방법

### 1단계: Gmail 뉴스레터 파싱 테스트
현재 1단계가 구현되었습니다. 테스트 방법:

```bash
python main.py
```

이 명령어는:
- Gmail에 접속하여 최근 24시간 이내 TLDR 메일을 검색
- HTML 본문에서 기사 제목, 요약, 링크를 추출
- 콘솔에 추출된 기사들을 출력
- `logs/newsletter_summary.log`에 로그 기록

### 예상 출력
```
추출된 기사: 15개
================================================================================

1. AI의 미래: GPT-5 출시 예정
   링크: https://example.com/ai-future
   요약: OpenAI가 2025년에 GPT-5를 출시할 예정이라고 발표했습니다...
--------------------------------------------------------------------------------
```

## 문제 해결

### Gmail 연결 오류
```
error: Gmail 연결 실패: [Errno 8] nodename nor servname provided, or not known
```
- 인터넷 연결 확인
- 방화벽 설정 확인

### 로그인 오류
```
error: LOGIN failed
```
- 앱 비밀번호가 올바른지 확인 (16자리)
- Gmail 계정의 2단계 인증 활성화 확인

### 메일을 찾을 수 없음
```
경고: 최근 24시간 이내 TLDR 메일이 없습니다.
```
- Gmail에서 TLDR 메일이 실제로 수신되었는지 확인
- `TLDR_SENDER_EMAIL` 설정이 올바른지 확인

## 다음 단계
- [ ] 2단계: Azure OpenAI 요약 기능 구현
- [ ] 3단계: Gmail SMTP 자동 발송 구현
- [ ] 4단계: 스케줄링 및 통합

## 라이선스
MIT License

