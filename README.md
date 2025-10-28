# 📰 인재육성팀 AI 뉴스레터 자동화 시스템

TLDR AI 뉴스레터를 자동으로 파싱하여 요약하고, 한국어로 재작성하여 회사 메일로 발송하는 자동화 시스템입니다.

## ✨ 주요 기능

- **Gmail 자동 파싱**: TLDR 뉴스레터를 IMAP으로 받아 자동 처리
- **Azure OpenAI 요약**: GPT-4를 활용하여 핵심 내용 추출 및 한국어 재작성
- **스토리텔링 방식**: 읽기 즐겁고 친근한 톤으로 작성
- **자동 이메일 발송**: 여러 수신자에게 HTML 형식의 이쁜 메일 자동 발송
- **시각적 디자인**: 색상, 레이아웃, 형식을 조정해 가독성 향상
- **중복 방지**: Sponsor 광고 필터링 및 정확한 기사만 추출

## 📁 프로젝트 구조

```
newpick/
├── main.py              # 메인 실행 파일 (파싱, 요약, 발송)
├── config.py            # 설정 파일 (API 키, 이메일 등)
├── requirements.txt     # Python 패키지 의존성
├── README.md            # 이 파일
└── logs/                # 로그 디렉토리
    └── newsletter_summary.log
```

## 🚀 설치 및 설정

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 설정 파일 생성

`config.py`를 생성하고 다음 정보를 입력하세요:

```python
# ==================== Gmail 설정 ====================
GMAIL_EMAIL = "your_email@gmail.com"
GMAIL_APP_PASSWORD = "your_16_char_app_password"

# 받는 사람 설정 (여러 명 가능)
RECIPIENT_EMAILS = [
    "recipient1@company.com",
    "recipient2@company.com"
]

# TLDR 발신자 설정
TLDR_SENDER_EMAILS = [
    "dan@tldrnewsletter.com"  # TLDR 뉴스레터 발신 주소
]

# ==================== Azure OpenAI 설정 ====================
AZURE_OPENAI_ENDPOINT = "https://your-endpoint.openai.azure.com"
AZURE_OPENAI_API_KEY = "your-api-key"
AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4"  # 또는 사용할 모델명
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"

# 기타 설정
LOG_DIR = "logs"
LOG_FILE = "newsletter_summary.log"
```

### 3. Gmail 앱 비밀번호 생성

1. [Google 계정 관리](https://myaccount.google.com) → 보안
2. 2단계 인증 활성화
3. 앱 비밀번호 생성: [여기서 생성](https://myaccount.google.com/apppasswords)
4. 생성된 16자리 비밀번호를 `GMAIL_APP_PASSWORD`에 입력

## 📖 사용 방법

### 실행

```bash
python main.py
```

### 동작 과정

1. **Gmail 접속**: IMAP으로 최근 72시간 내 TLDR 메일 검색
2. **기사 추출**: HTML 구조를 파싱하여 제목, 요약, 링크 추출 (Sponsor 광고 제외)
3. **AI 요약**: Azure OpenAI로 2-3개 핵심 기사만 선별하여 한국어로 재작성
   - 스토리텔링 방식: 친근하고 읽기 좋은 톤
   - 구체적 예시와 비유 사용
   - 충분한 설명 제공
4. **HTML 변환**: 다채로운 색상과 레이아웃으로 시각적 디자인
5. **메일 발송**: 수신자에게 자동 발송

### 예상 출력

```
2025-10-28 13:40:57 - INFO - 추출된 기사 수: 13
2025-10-28 13:40:57 - INFO - 총 13개의 기사 추출 완료
2025-10-28 13:41:08 - INFO - Azure OpenAI 요약 완료
2025-10-28 13:41:18 - INFO - 메일 발송 완료: recipient1@company.com, recipient2@company.com

✅ 요약 메일이 recipient1@company.com, recipient2@company.com로 발송되었습니다!
```

## 🎨 디자인 특징

### 시각적 개선
- **컬러풀한 섹션**: 각 기사별로 다른 색상(파란색, 주황색, 보라색, 초록색)
- **그림자 효과**: 헤더와 버튼에 입체감 추가
- **그라데이션**: 헤더와 버튼에 그라데이션 배경 적용
- **적절한 간격**: 읽기 편한 줄 간격(1.8)과 여백
- **버튼 스타일**: 클릭하기 쉬운 큰 버튼 디자인

### 톤 & 스타일
- 구어체 사용: "~거예요", "~하시나요?", "~고 있답니다!"
- 이모지 활용: 🎉 🔥 💡 🚀 💰 등
- 친근한 어조: 친구에게 소식을 전하는 느낌
- 구체적 설명: 기술 용어를 일상 비유로 설명

## 🔧 주요 개선 사항

### v1.0 (현재)
- ✅ TLDR 뉴스레터 파싱
- ✅ Azure OpenAI 기반 한국어 요약
- ✅ 자동 이메일 발송
- ✅ HTML 기반 예쁜 디자인
- ✅ Sponsor 광고 필터링
- ✅ 섹션별 다른 색상 적용

## 🐛 문제 해결

### Gmail 연결 실패
```
error: Gmail 연결 실패
```
- 인터넷 연결 확인
- 앱 비밀번호가 올바른지 확인 (16자리)
- Gmail 2단계 인증 활성화 확인

### 메일을 찾을 수 없음
```
경고: 최근 TLDR 메일이 없습니다.
```
- Gmail에서 실제로 메일이 수신되었는지 확인
- `TLDR_SENDER_EMAILS` 설정이 올바른지 확인
- 최근 72시간 내 메일이 있는지 확인

### Azure OpenAI 오류
```
error: Azure OpenAI API 오류
```
- API 키가 올바른지 확인
- 엔드포인트 URL 확인
- Deployment 이름 확인

## 📝 로그 확인

로그 파일 위치: `logs/newsletter_summary.log`

```bash
# 로그 확인
tail -f logs/newsletter_summary.log

# 최근 로그만 보기
tail -20 logs/newsletter_summary.log
```

## 🚀 향후 계획

- [ ] 스케줄링 기능 (cron)
- [ ] 중복 메일 처리 방지 (처리된 메일 추적)
- [ ] 에러 핸들링 강화 (재시도 로직)
- [ ] 다양한 뉴스레터 소스 지원
- [ ] 웹 대시보드 (발송 이력 확인)

## 📄 라이선스

MIT License

## 👥 기여자

인재육성팀
