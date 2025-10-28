import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import logging
import os
from typing import List, Dict, Any
from openai import AzureOpenAI
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
try:
    import config
except ImportError:
    print("❌ config.py 파일이 없습니다!")
    print("config.example.py를 복사하여 config.py를 생성하고 설정을 입력하세요.")
    print("명령어: cp config.example.py config.py")
    exit(1)

# 로깅 설정
os.makedirs(config.LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(config.LOG_DIR, config.LOG_FILE)),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def connect_gmail() -> imaplib.IMAP4_SSL:
    """
    Gmail IMAP 서버에 연결
    
    Returns:
        imaplib.IMAP4_SSL: IMAP 연결 객체
    
    Raises:
        Exception: 연결 실패 시
    """
    try:
        logger.info("Gmail IMAP 서버에 연결 중...")
        mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
        mail.login(config.GMAIL_EMAIL, config.GMAIL_APP_PASSWORD)
        logger.info("Gmail 연결 성공")
        return mail
    except Exception as e:
        logger.error(f"Gmail 연결 실패: {e}")
        raise


def search_recent_emails(mail: imaplib.IMAP4_SSL, senders: List[str], hours: int = 24) -> List[str]:
    """
    최근 N시간 이내 특정 발신자들로부터 온 메일 검색
    
    Args:
        mail: IMAP 연결 객체
        senders: 발신자 이메일 리스트
        hours: 몇 시간 이내의 메일을 검색할지
    
    Returns:
        List[str]: 메일 ID 리스트
    """
    try:
        # 메일박스 선택
        mail.select('inbox')
        
        # 최근 N시간 이내
        since_date = (datetime.now() - timedelta(hours=hours)).strftime("%d-%b-%Y")
        
        all_email_ids = []
        
        # 각 발신자별로 검색
        for sender in senders:
            # 발신자 검색
            search_query = f'(SINCE {since_date} FROM "{sender}")'
            logger.info(f"검색 쿼리: {search_query}")
            
            status, messages = mail.search(None, search_query)
            
            if status != 'OK':
                logger.warning(f"메일 검색 실패 (발신자: {sender})")
                continue
            
            email_ids = messages[0].split()
            logger.info(f"발신자 {sender}에서 검색된 메일 수: {len(email_ids)}")
            
            all_email_ids.extend(email_ids)
        
        # 중복 제거 및 정렬 (최신 메일이 마지막에 오도록)
        unique_ids = list(set(all_email_ids))
        # email_id를 정수로 변환하여 정렬
        unique_ids = sorted(unique_ids, key=lambda x: int(x))
        logger.info(f"전체 검색된 메일 수: {len(unique_ids)} (최신 메일만 처리 예정)")
        
        return unique_ids
    
    except Exception as e:
        logger.error(f"메일 검색 중 오류: {e}")
        return []


def decode_email_header(header) -> str:
    """
    이메일 헤더 디코딩
    
    Args:
        header: 인코딩된 헤더 문자열 또는 None
    
    Returns:
        str: 디코딩된 문자열
    """
    if header is None:
        return ""
    
    try:
        decoded_header = decode_header(str(header))
        decoded_str = ""
        for part, encoding in decoded_header:
            if isinstance(part, bytes):
                try:
                    decoded_str += part.decode(encoding or 'utf-8')
                except (UnicodeDecodeError, LookupError):
                    decoded_str += part.decode('utf-8', errors='ignore')
            else:
                decoded_str += str(part)
        return decoded_str
    except Exception as e:
        logger.warning(f"헤더 디코딩 실패: {e}")
        return str(header) if header else ""


def get_email_body(msg: email.message.EmailMessage) -> str:
    """
    이메일 본문 추출
    
    Args:
        msg: 이메일 메시지 객체
    
    Returns:
        str: HTML 본문
    """
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/html":
                charset = part.get_content_charset()
                body = part.get_payload(decode=True)
                if body:
                    try:
                        body = body.decode(charset or 'utf-8')
                    except:
                        body = body.decode('utf-8', errors='ignore')
                    break
    else:
        content_type = msg.get_content_type()
        if content_type == "text/html":
            charset = msg.get_content_charset()
            body = msg.get_payload(decode=True)
            if body:
                try:
                    body = body.decode(charset or 'utf-8')
                except:
                    body = body.decode('utf-8', errors='ignore')
    
    return body


def extract_articles_from_html(html: str) -> List[Dict[str, Any]]:
    """
    HTML에서 TLDR 뉴스레터 기사 추출 (개선된 버전 2)
    <table> 블록 단위로 기사를 파싱
    
    구조:
    <table>
      <a href="링크">
        <strong>제목</strong>
      </a>
      <br><br>
      <span style="font-family:...">요약</span>
    </table>
    
    Args:
        html: HTML 본문
    
    Returns:
        List[Dict[str, Any]]: 추출된 기사 리스트
            각 기사는 {'title': str, 'summary': str, 'link': str} 형식
    """
    articles = []
    
    try:
        soup = BeautifulSoup(html, 'lxml')
        
        # 모든 <table> 블록 찾기
        tables = soup.find_all('table', align='center')
        
        for table in tables:
            # <a> 태그 찾기
            link_tag = table.find('a', href=True)
            if not link_tag:
                continue
            
            link_url = link_tag.get('href')
            if not link_url or 'http' not in link_url:
                continue
            
            # tldr.tech 관련 링크는 제외
            if 'tldr.tech' in link_url or 'techplatforms.com' in link_url:
                continue
            
            # <strong> 태그에서 제목 추출
            strong_tag = link_tag.find('strong')
            if not strong_tag:
                continue
            
            title = strong_tag.get_text(strip=True)
            
            # Sponsor 광고 제외
            if '(Sponsor)' in title or title.startswith('Looking for a practical') or title.startswith('Get it free') or title.startswith('Try it free') or title.startswith('Together With'):
                continue
            
            # 모든 <span> 태그에서 요약 찾기
            spans = table.find_all('span')
            summary = ""
            
            for span in spans:
                style = span.get('style', '')
                span_text = span.get_text(strip=True)
                
                # font-family가 있는 span이 요약일 가능성 높음
                if 'font-family' in style and len(span_text) > 30:
                    # strong 태그 제목과 다른 경우만 요약으로
                    if span_text != title:
                        summary = span_text
                        break
            
            # 요약이 없으면 제목 사용
            if not summary:
                summary = title[:200]
            
            # 중복 체크
            if not any(article['link'] == link_url for article in articles):
                articles.append({
                    'title': title,
                    'summary': summary[:300],
                    'link': link_url
                })
        
        logger.info(f"추출된 기사 수: {len(articles)}")
        
        # 너무 많은 기사가 있으면 줄이기 (최대 20개)
        return articles[:20]
    
    except Exception as e:
        logger.error(f"HTML 파싱 중 오류: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def fetch_tldr_newsletter() -> List[Dict[str, Any]]:
    """
    TLDR 뉴스레터를 Gmail에서 가져와서 기사 추출
    
    Returns:
        List[Dict[str, Any]]: 추출된 기사 리스트
    """
    mail = None
    articles = []
    
    try:
        # Gmail 연결
        mail = connect_gmail()
        
        # 최근 72시간(3일) 이내 TLDR 메일 검색 (주말 제외하고 평일 메일 찾기)
        email_ids = search_recent_emails(mail, config.TLDR_SENDER_EMAILS, hours=72)
        
        if not email_ids:
            logger.warning("최근 TLDR 메일이 없습니다.")
            return articles
        
        # 가장 최근 메일만 처리 (리스트 중 마지막 것이 최신)
        latest_email_id = email_ids[-1] if isinstance(email_ids, list) else email_ids.split()[-1]
        logger.info(f"처리할 메일 ID: {latest_email_id}")
        
        # 메일 가져오기
        status, msg_data = mail.fetch(latest_email_id, '(RFC822)')
        
        if status != 'OK':
            logger.error("메일 가져오기 실패")
            return articles
        
        # 메시지 파싱
        raw_email = msg_data[0][1]
        
        # bytes 확인 및 처리
        if isinstance(raw_email, bytes):
            msg = email.message_from_bytes(raw_email)
        else:
            msg = raw_email
        
        # 제목 추출
        subject = decode_email_header(msg["Subject"])
        logger.info(f"메일 제목: {subject}")
        
        # HTML 본문 추출
        html_body = get_email_body(msg)
        
        if not html_body:
            logger.warning("HTML 본문을 찾을 수 없습니다.")
            return articles
        
        # HTML에서 기사 추출
        articles = extract_articles_from_html(html_body)
        
        logger.info(f"총 {len(articles)}개의 기사 추출 완료")
        
        return articles
    
    except Exception as e:
        logger.error(f"TLDR 뉴스레터 가져오기 중 오류: {e}")
        return articles
    
    finally:
        if mail:
            mail.logout()
            logger.info("Gmail 연결 종료")


def init_azure_openai() -> AzureOpenAI:
    """
    Azure OpenAI 클라이언트 초기화
    
    Returns:
        AzureOpenAI: Azure OpenAI 클라이언트
    """
    try:
        import httpx
        import os
        
        # 기존 환경변수 백업 및 제거 (proxies 관련 충돌 방지)
        old_base_url = os.environ.pop('OPENAI_BASE_URL', None)
        old_api_key = os.environ.pop('OPENAI_API_KEY', None)
        
        try:
            # Azure OpenAI 엔드포인트에서 마지막 슬래시 제거
            endpoint = config.AZURE_OPENAI_ENDPOINT.rstrip('/')
            
            # httpx 클라이언트를 직접 생성하여 proxies 인자 문제 회피
            http_client = httpx.Client()
            
            client = AzureOpenAI(
                api_key=config.AZURE_OPENAI_API_KEY,
                api_version=config.AZURE_OPENAI_API_VERSION,
                azure_endpoint=endpoint,
                azure_deployment=config.AZURE_OPENAI_DEPLOYMENT_NAME,
                http_client=http_client
            )
            logger.info("Azure OpenAI 클라이언트 초기화 완료")
            return client
        finally:
            # 환경변수 복원
            if old_base_url:
                os.environ['OPENAI_BASE_URL'] = old_base_url
            if old_api_key:
                os.environ['OPENAI_API_KEY'] = old_api_key
    except Exception as e:
        import traceback
        logger.error(f"Azure OpenAI 클라이언트 초기화 실패: {e}")
        logger.error(f"엔드포인트: {config.AZURE_OPENAI_ENDPOINT}")
        logger.error(f"상세 에러: {traceback.format_exc()}")
        raise


def summarize_articles(client: AzureOpenAI, articles: List[Dict[str, Any]]) -> str:
    """
    추출된 기사들을 Azure OpenAI로 한국어 요약
    
    Args:
        client: Azure OpenAI 클라이언트
        articles: 추출된 기사 리스트
    
    Returns:
        str: 요약된 내용
    """
    try:
        logger.info("Azure OpenAI로 기사 요약 시작...")
        
        # 기사 내용 준비
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"\n{i}. {article['title']}\n"
            articles_text += f"   요약: {article['summary']}\n"
            articles_text += f"   링크: {article['link']}\n"
        
        # Azure OpenAI 프롬프트
        prompt = f"""다음은 TLDR 뉴스레터에서 추출한 기술 뉴스 기사들입니다 (이미 요약본입니다).
이 중에서 가장 중요하고 흥미로운 2-3개 기사만 선별하여, 독자가 정말 재미있게 읽을 수 있는 스토리텔링 방식으로 재작성해주세요.

원본 기사들:
{articles_text}

요구사항:
1. 총 20개 기사 중 가장 중요하고 흥미로운 **2-3개만** 선별
2. **스토리텔링 방식**으로 작성 - 마치 친구에게 재미있는 소식을 전하는 것처럼!
   - 시작: 일상적인 상황이나 질문으로 독자를 끌어들이기
   - 본문: 구체적인 예시와 비유를 사용하여 설명
   - 마무리: 실제 영향력과 의미를 강조
3. **톤 & 스타일**:
   - 편안하고 친근한 말투 사용
   - "~데요", "~거예요", "~하네요" 같은 구어체 활용
   - 감탄사와 이모지 적극 활용 (🎉 🔥 💡 🚀 💰 ⚡ 등)
   - 매우 사적인 스타일: "~하시나요?", "~줄 아세요?", "~고 있답니다!"
4. **내용 구성**:
   - 각 기사마다 2-3개 문단으로 구성
   - 1문단: 인트로 (독자 관심 유도)
   - 2문단: 핵심 내용 (구체적 예시와 함께)
   - 3문단: 영향력과 의미 (무엇이 변하는지)
5. 기술 용어는 반드시 **일상 예시와 비유**로 설명
   - 예: "AI 모델 = 사람 뇌를 컴퓨터에 넣은 것"
   - 예: "GPU = 그림 그리는 고속 버스"
6. 원본이 광고나 후원 게시물이면 제외
7. 각 기사는 **최소 250자 이상**으로 충분히 상세하게 작성

중요: 응답은 반드시 다음 형식을 정확히 따라야 합니다. 

```html
<h1>🎯 오늘 챙겨볼 AI 소식 (2-3선)</h1>

<h2>[섹션 1] [눈에 띄는 제목 - 이모지 포함]</h2>
<p>[독자의 흥미를 유발하는 한 줄 인트로]</p>
<p>[기술 설명 및 핵심 내용을 흥미롭게 재작성 - 충분히 길게]</p>
<p><a href="URL링크">🔗 자세히 보기</a></p>

<h2>[섹션 2] [눈에 띄는 제목 - 이모지 포함]</h2>
<p>[내용]</p>
<p>[내용]</p>
<p><a href="URL링크">🔗 자세히 보기</a></p>
```

응답은 꼭 위 HTML 형식으로 작성해주세요. 마크다운이 아닌 HTML 태그를 사용해야 합니다.
"""
        
        # Azure OpenAI API 호출
        response = client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {
                    "role": "system",
                    "content": """당신은 기술 뉴스를 아주 재미있고 읽기 좋게 스토리텔링하는 전문가입니다.

작성 스타일:
- 편안하고 친근한 구어체 사용 ("~거예요", "~하시나요?", "~고 있답니다!")
- 구체적인 예시와 비유를 많이 사용
- 감탄사와 이모지 적극 활용
- 마치 친구에게 흥미로운 소식을 알려주는 것처럼 작성
- 기술적 내용도 일상 언어로 쉽게 설명

독자가 "음... 이거 재밌네?!"라고 생각하며 끝까지 읽고 싶어지는 글이 되어야 합니다."""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.9,  # 더 창의적이고 재미있게
            max_tokens=4500
        )
        
        summary = response.choices[0].message.content
        logger.info("Azure OpenAI 요약 완료")
        
        # 코드블록 제거 (```html과 ```를 제거)
        import re
        summary = re.sub(r'```html\s*\n?', '', summary)
        summary = re.sub(r'```\s*$', '', summary, flags=re.MULTILINE)
        summary = summary.strip()
        
        return summary
    
    except Exception as e:
        logger.error(f"Azure OpenAI 요약 중 오류: {e}")
        raise


def print_extracted_articles(articles: List[Dict[str, Any]]):
    """
    추출된 기사들을 출력
    
    Args:
        articles: 추출된 기사 리스트
    """
    print("\n" + "="*80)
    print(f"추출된 기사: {len(articles)}개")
    print("="*80)
    
    for i, article in enumerate(articles, 1):
        print(f"\n{i}. {article['title']}")
        print(f"   링크: {article['link']}")
        if article['summary']:
            print(f"   요약: {article['summary'][:100]}...")
        print("-" * 80)


def print_summary(summary: str):
    """
    요약 내용을 출력
    
    Args:
        summary: 요약된 내용
    """
    print("\n" + "="*80)
    print("📰 Azure OpenAI 요약 결과")
    print("="*80)
    print(summary)
    print("="*80)


def format_ai_html(html_text: str) -> str:
    """
    AI가 반환한 HTML에 스타일을 추가하여 완전한 HTML로 변환
    - 더 나은 가독성을 위한 다채로운 스타일링
    - 줄바꿈과 단락 구분 개선
    - 색상과 크기 다양화
    """
    import re
    
    # AI가 HTML 태그를 사용했는지 확인
    if '<h1>' in html_text or '<h2>' in html_text:
        # 이미 HTML 형식인 경우 - 개선된 스타일 추가
        html = html_text
        
        # h1 스타일 추가 (더 눈에 띄게)
        html = re.sub(r'<h1>(.+?)</h1>', 
                      r'<h1 style="color: #4CAF50; font-size: 28px; margin: 30px 0 25px; font-weight: bold; text-align: center; border-bottom: 3px solid #4CAF50; padding-bottom: 15px;">\1</h1>', 
                      html, flags=re.DOTALL)
        
        # h2 스타일 추가 (다양한 색상으로)
        # 섹션별로 다른 색상 적용
        section_num = 0
        def replace_h2(match):
            nonlocal section_num
            content = match.group(1)
            colors = [
                ('#2196F3', '#E3F2FD'),  # 파란색
                ('#FF9800', '#FFF3E0'),  # 주황색
                ('#9C27B0', '#F3E5F5'),  # 보라색
                ('#4CAF50', '#E8F5E9'),  # 초록색
            ]
            color, bg_color = colors[section_num % len(colors)]
            section_num += 1
            return f'<h2 style="color: {color}; font-size: 22px; margin: 30px 0 15px; padding: 12px 15px; background: linear-gradient(90deg, {bg_color} 0%, #FFFFFF 100%); border-left: 5px solid {color}; border-radius: 5px; font-weight: bold;">{content}</h2>'
        
        html = re.sub(r'<h2>(.+?)</h2>', replace_h2, html, flags=re.DOTALL)
        
        # p 태그에 스타일 추가 (줄 간격, 여백 개선)
        html = re.sub(r'<p>(.+?)</p>', 
                      r'<p style="margin: 0 0 18px 0; line-height: 1.8; color: #333; font-size: 16px; text-align: justify; padding: 0 10px;">\1</p>', 
                      html, flags=re.DOTALL)
        
        # a 태그 스타일 추가 (더 눈에 띄는 버튼)
        html = re.sub(r'<a href="([^"]+)">(.+?)</a>', 
                      r'<a href="\1" style="color: #4CAF50; text-decoration: none; padding: 12px 20px; background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%); border-radius: 8px; display: inline-block; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1); transition: all 0.3s;">\2</a>', 
                      html, flags=re.DOTALL)
    else:
        # 마크다운 형식인 경우 (하위 호환성)
        html = html_text
        html = html.replace('# 🎯 오늘 챙겨볼 AI 소식 (2-3선)', '<h1 style="color: #4CAF50; font-size: 28px; margin: 30px 0 25px; font-weight: bold; text-align: center; border-bottom: 3px solid #4CAF50; padding-bottom: 15px;">🎯 오늘 챙겨볼 AI 소식 (2-3선)</h1>')
        html = re.sub(r'^## (.+)$', r'<h2 style="color: #2196F3; font-size: 22px; margin: 30px 0 15px; padding: 12px 15px; background: linear-gradient(90deg, #E3F2FD 0%, #FFFFFF 100%); border-left: 5px solid #2196F3; border-radius: 5px; font-weight: bold;">\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'🔗 \[([^\]]+)\]\(([^\)]+)\)', r'<p style="margin: 10px 0;"><a href="\2" style="color: #4CAF50; text-decoration: none; padding: 12px 20px; background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%); border-radius: 8px; display: inline-block; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">🔗 \1</a></p>', html)
        
        # 단락 처리 (더 넓은 간격)
        paragraphs = html.split('\n\n')
        formatted_paragraphs = []
        for para in paragraphs:
            para = para.strip()
            if para and not para.startswith('<h') and not para.startswith('<p') and para:
                para = f'<p style="margin: 0 0 20px 0; line-height: 1.8; color: #333; font-size: 16px; text-align: justify;">{para}</p>'
            formatted_paragraphs.append(para)
        html = '\n'.join(formatted_paragraphs)
    
    return html


def send_summary_email(summary: str):
    """
    요약 내용을 메일로 발송
    
    Args:
        summary: 요약된 내용 (마크다운 형식)
    """
    try:
        logger.info("메일 발송 시작...")
        
        # AI가 반환한 내용을 HTML로 변환
        html_summary = format_ai_html(summary)
        
        # 메일 본문 작성 (HTML 형식)
        html_body = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ 
                        font-family: 'Apple SD Gothic Neo', -apple-system, 'Segoe UI', sans-serif; 
                        line-height: 1.8; 
                        color: #333; 
                        background-color: #f5f5f5;
                        margin: 0;
                        padding: 0;
                    }}
                    .container {{ 
                        max-width: 700px; 
                        margin: 20px auto; 
                        background: white;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                        border-radius: 8px;
                        overflow: hidden;
                    }}
                    .header {{ 
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white; 
                        padding: 50px 30px; 
                        text-align: center;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 32px;
                        font-weight: bold;
                        text-shadow: 0 2px 4px rgba(0,0,0,0.2);
                        letter-spacing: 0.5px;
                    }}
                    .header p {{
                        margin: 15px 0 0;
                        font-size: 16px;
                        opacity: 0.95;
                        font-weight: 300;
                        letter-spacing: 0.3px;
                    }}
                    .content {{ 
                        padding: 40px 30px; 
                        background: white;
                    }}
                    h2 {{
                        margin-top: 30px !important;
                        margin-bottom: 15px !important;
                        font-size: 22px;
                    }}
                    p {{
                        margin: 12px 0;
                        color: #444;
                        font-size: 16px;
                    }}
                    .content {{
                        font-size: 16px;
                    }}
                    a {{
                        color: #4CAF50;
                        text-decoration: none;
                        transition: all 0.3s;
                    }}
                    a:hover {{
                        text-decoration: underline;
                    }}
                    .footer {{ 
                        margin-top: 50px; 
                        padding: 30px 25px; 
                        border-top: 3px solid #e0e0e0; 
                        text-align: center; 
                        color: #666; 
                        font-size: 15px; 
                        background: linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%);
                        border-radius: 0 0 8px 8px;
                    }}
                    .footer p {{
                        margin: 5px 0;
                        font-style: italic;
                        letter-spacing: 0.5px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>📰 인재육성팀 AI 뉴스레터</h1>
                        <p>{datetime.now().strftime('%Y년 %m월 %d일')}</p>
                    </div>
                    <div class="content">
                        {html_summary}
                        <div class="footer">
                            <p>✨ 오늘도 행복한 하루 보내세요 ✨</p>
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """
        
        # 메일 발송 (여러 수신자)
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'🤖 [인재육성팀] AI 뉴스레터 - {datetime.now().strftime("%Y년 %m월 %d일")}'
        msg['From'] = config.GMAIL_EMAIL
        msg['To'] = ', '.join(config.RECIPIENT_EMAILS)
        
        # HTML 본문 추가
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)
        
        # SMTP 서버 연결 및 발송
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(config.GMAIL_EMAIL, config.GMAIL_APP_PASSWORD)
            text = msg.as_string()
            
            # 모든 수신자에게 발송
            for recipient in config.RECIPIENT_EMAILS:
                server.sendmail(config.GMAIL_EMAIL, recipient, text)
        
        recipients_str = ', '.join(config.RECIPIENT_EMAILS)
        logger.info(f"메일 발송 완료: {recipients_str}")
        print(f"\n✅ 요약 메일이 {recipients_str}로 발송되었습니다!")
    
    except Exception as e:
        logger.error(f"메일 발송 중 오류: {e}")
        raise


if __name__ == "__main__":
    logger.info("="*80)
    logger.info("TLDR 뉴스레터 파싱 시작")
    logger.info("="*80)
    
    # TLDR 뉴스레터 가져오기
    articles = fetch_tldr_newsletter()
    
    # 결과 출력
    if articles:
        print_extracted_articles(articles)
        
        # Azure OpenAI로 요약
        summary = None
        try:
            client = init_azure_openai()
            summary = summarize_articles(client, articles)
            print_summary(summary)
            logger.info("TLDR 뉴스레터 파싱 및 요약 완료")
        except Exception as e:
            logger.error(f"요약 중 오류 발생: {e}")
            print("\n⚠️ 요약 기능을 건너뜁니다. 기사만 표시합니다.")
        
        # 요약이 있으면 메일 발송
        if summary:
            try:
                send_summary_email(summary)
            except Exception as e:
                logger.error(f"메일 발송 중 오류: {e}")
                print("\n⚠️ 메일 발송에 실패했습니다.")
    else:
        logger.warning("추출된 기사가 없습니다.")
    
    logger.info("="*80)

