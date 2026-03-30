# Product Name Parser

## 프로젝트 개요
골프 용품 주문목록 엑셀 파일의 상품명을 브랜드/메인모델/서브모델/카테고리/기타태그로 분류하는 Streamlit 앱.

## 실행 방법
```bash
streamlit run app.py
```

## 프로젝트 구조
```
product_name_parser/
├── app.py                  # Streamlit 메인 (파일 업로드, 파싱, 다운로드)
├── data/
│   └── dictionary.json     # 브랜드/모델/카테고리/태그 사전 (앱에서 편집 가능)
├── golf_parser/
│   ├── normalizer.py       # 텍스트 정규화 (노이즈 제거, 브라켓 처리)
│   ├── matcher.py          # 사전 매칭 로직 (우선순위 기반)
│   └── parser.py           # ProductNameParser 클래스
└── pages/
    ├── 1_사전관리.py         # 브랜드/모델/카테고리/태그 CRUD
    └── 2_미분류검토.py       # 미분류 항목 검토 및 사전 등록
```

## 파싱 파이프라인
1. 태그 추출 (시타채, 좌타, 성별, 임직원 등)
2. 노이즈 제거 (증정, GF, 정품, 연도 등)
3. 브랜드 추출 (본문 우선, 브라켓 힌트 fallback)
4. 카테고리 추출 (우선순위 기반 — 커버 > 파우치 > 가방 > 클럽류)
5. 모델/서브모델 추출 (해당 브랜드 사전 기준)
6. 잔여 텍스트 = 미분류 모델명 후보

## 핵심 설계 결정사항

### 브랜드-모델 계층 구조
- 브랜드 → 메인모델 → 서브모델 (종속 관계)
- 오딧세이는 캘러웨이 소속이라도 독립 브랜드로 등록

### 카테고리 우선순위 (priority 필드)
- 여러 카테고리 키워드가 상품명에 동시에 등장할 때 높은 priority가 우선
- 예: "드라이버 커버" → priority 20인 커버가 priority 5인 드라이버를 이김
- 기본값: 커버(20), 파우치(15), 가방(10), 모자/장갑/신발(8), 클럽류/골프공(5), 악세사리(3)

### 매칭 규칙
- 모든 알파벳 매칭은 대소문자 무시 (case-insensitive)
- 각 엔티티는 `aliases` 리스트로 다양한 표현 지원 (예: XXIO / 젝시오)
- `name` 필드가 표시명이자 정규 이름 (별도 display 필드 없음)
- 최장 매칭(longest match) 우선, 동일 우선순위면 더 긴 alias가 승리

### 분류 상태
- 완료: 브랜드 + 카테고리 모두 매칭
- 부분: 둘 중 하나만 매칭
- 미분류: 둘 다 매칭 안 됨

## dictionary.json 구조
```json
{
  "brands": [
    {
      "name": "캘러웨이",
      "aliases": ["callaway", "한국캘러웨이"],
      "models": [
        {
          "name": "QI4D",
          "aliases": ["qi4d"],
          "sub_models": [
            { "name": "MAX", "aliases": ["맥스"] }
          ]
        }
      ]
    }
  ],
  "categories": [
    { "name": "커버", "priority": 20, "aliases": ["커버", "cover", "헤드커버"] }
  ],
  "tags": {
    "남성": ["남성", "남성용", "men"]
  },
  "noise_patterns": ["증정", "GF"]
}
```
