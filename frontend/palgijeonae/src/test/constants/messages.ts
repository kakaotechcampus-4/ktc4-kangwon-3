import { SocialProvider } from '@/api/users'
import { PROCESSING_STATUS_LABELS } from '@/pages/Judgement/utils/processingStatusLabels'
import { NAME_MAX_LENGTH } from '@/pages/Mypage/constants'
import { SOCIAL_PROVIDER_INFO } from '@/pages/Mypage/utils/socialProvider'
import { ALLOWED_IMAGE_EXTENSIONS_LABEL, MAX_FILE_SIZE_MB } from '@/pages/Upload/constants'

// 통합 테스트가 비교하는 알림·안내 문구를 화면별로 모아 둔다. 문구가 바뀌면 이 파일만 고친다.
// - 소스에서 export된 상수가 있으면 그것을 import해서 쓴다. (소스가 바뀌면 테스트도 따라간다)
// - 소스에 export가 없는 문구만 이 파일에 직접 적고 `NOTE(source)`를 단다. (소스가 export하면 이 정의를 지운다)
// - 테스트가 MSW 응답에 직접 넣는 서버 메시지는 화면 문구가 아니므로 SERVER_MESSAGES에 따로 둔다.

// 여러 화면이 같은 문구로 알리는 잘못된 접근 안내
export const COMMON_MESSAGES = {
  // NOTE(source): Judgement·Question 화면의 alert 문구. 소스에 export가 없다.
  INVALID_ACCESS_TO_UPLOAD: '잘못된 접근입니다. 진단서를 업로드한 후 다시 시도해주세요.',
  // NOTE(source): Question·Result 화면의 alert 문구. 소스에 export가 없다.
  INVALID_ACCESS: '잘못된 접근입니다.',
}

export const POLICY_MESSAGES = {
  // NOTE(source): NotFound 화면의 문구. 소스에 export가 없다.
  NOT_FOUND: '404 - 페이지를 찾을 수 없습니다.',
}

export const UPLOAD_MESSAGES = {
  // NOTE(source): validation.ts의 오류 문구. 소스에 export가 없다.
  TITLE_REQUIRED: '제품명을 입력해주세요.',
  LINK_REQUIRED: '상세페이지 링크를 입력해주세요.',
  LINK_MUST_BE_HTTP: '상세페이지 링크는 http:// 또는 https://로 시작해야 합니다.',
  CONTENT_REQUIRED: '상세페이지 내용을 입력해주세요.',
  // 허용 형식·용량은 소스의 제한 상수에서 만든다.
  IMAGE_TYPE_NOT_ALLOWED: `${ALLOWED_IMAGE_EXTENSIONS_LABEL} 형식의 이미지만 첨부할 수 있습니다.`,
  IMAGE_TOO_LARGE: `이미지는 1장당 ${MAX_FILE_SIZE_MB}MB까지만 첨부할 수 있습니다.`,
  // NOTE(source): Upload 화면의 alert·안내 문구. 소스에 export가 없다.
  NO_PRODUCTS: '진단할 상품을 먼저 추가해주세요.',
  MAX_PRODUCTS_REACHED: '상품은 최대 10개까지 담을 수 있어요. 진단을 시작해주세요.',
  // 제출 전 검증에 걸린 상품: "상품 이름: 사유"
  invalidProduct: (productName: string, reason: string) => `${productName}: ${reason}`,
  // 상품별 이미지 업로드 실패 안내의 앞부분: "다음 상품의 진단 요청에 실패했습니다: 상품 이름(원인)"
  productRequestFailed: (productName: string) => `다음 상품의 진단 요청에 실패했습니다: ${productName}(`,
  // NOTE(source): 진단 요청 중 로딩 라벨
  SUBMITTING: '진단 요청을 보내는 중...',
}

export const QUESTION_MESSAGES = {
  // NOTE(source): Question 화면의 alert·안내 문구. 소스에 export가 없다.
  ANSWER_ALL: '질문에 모두 답변해 주세요.',
  NO_QUESTIONS: '확인이 필요한 질문이 없어요.',
  LOAD_FAILED: '질문을 불러오지 못했어요.',
  INVALID_PRODUCT_ID: '유효하지 않은 상품 id 입니다.',
  PROGRESS_COMPLETE: '답변 완료',
  roundTitle: (round: number) => `${round}차 질문`,
  progress: (answered: number, total: number) => `${answered}/${total}`,
}

export const JUDGEMENT_MESSAGES = {
  // 상태 배지·요약 바 라벨은 소스의 PROCESSING_STATUS_LABELS를 그대로 쓴다. (진행 중/답변 필요/완료/실패)
  STATUS_LABELS: PROCESSING_STATUS_LABELS,
  // NOTE(source): Judgement 화면의 alert·안내 문구. 소스에 export가 없다.
  NOT_FOUND: '유효하지 않은 진단서 id 입니다.',
  LOAD_FAILED: '진행 상황을 불러오지 못했어요.',
  EMPTY: '확인할 상품이 없어요.',
  REPORT_HINT_RUNNING: '진행 중인 상품이 끝나면 진단서를 볼 수 있어요.',
  REPORT_HINT_DONE: '페이지를 나가도 진단은 계속돼요. 마이페이지에서 다시 볼 수 있어요.',
  productCountIntro: (count: number) => `${count}개 상품을 동시에 확인하고 있어요`,
  // NOTE(source): statusNotice.ts / statusDescription.ts의 카드 문구. 소스에 export가 없다.
  AWAITING_INPUT_NOTICE: '답변하면 처음부터 다시 진단해요. 다른 상품은 기다리지 않고 계속 진행돼요.',
  STAGE_EXTRACTION: '상세페이지에서 상품 정보를 읽고 있어요.',
  awaitingInputQuestions: (count: number) => `확인이 필요한 질문 ${count}개`,
  // NOTE(source): ProgressBar의 단계 라벨
  PROGRESS_STEP_EXTRACTION: '상세페이지 읽기',
  // NOTE(source): useStatusAnnouncement의 스크린리더 안내 문구
  announceCompleted: (productName: string) => `${productName} 진단이 끝났어요`,
  ANNOUNCE_ALL_DONE: '모든 진단이 끝났어요. 진단서를 볼 수 있어요',
}

export const RESULT_MESSAGES = {
  // NOTE(source): bannerConfig.ts의 배너 설명. 소스에 export가 없다. (실패 원인은 줄바꿈 뒤에 이어 붙는다)
  RETRYABLE_FAILURE: '진단에 실패했어요. 다시 시도해 주세요.',
  NOT_RETRYABLE_FAILURE: '진단을 완료할 수 없어요.',
  UNKNOWN_FAILURE: '진단에 실패했어요.',
}

export const MYPAGE_MESSAGES = {
  // NOTE(source): Mypage 화면의 안내·확인·알림 문구. 소스에 export가 없다. (탈퇴 확인 문구는 WithdrawSection에서 export되지 않는다)
  EMPTY: '조건에 맞는 상품이 없어요.',
  LIST_LOAD_FAILED: '상품 목록을 불러오지 못했어요.',
  PROFILE_LOAD_FAILED: '회원 정보를 불러오지 못했어요.',
  deleteConfirm: (productName: string) => `'${productName}'의 진단 결과와 첨부 이미지가 함께 삭제되고, 되돌릴 수 없어요.`,
  // NOTE(source): RevisionNoticeBanner의 재진단 확인 문구. 소스에 export가 없다.
  rediagnoseConfirm: (productName: string) => `'${productName}'을(를) 다시 진단할까요? 이전 진단 결과는 사라지고, 되돌릴 수 없어요.`,
  WITHDRAW_CONFIRM_TITLE: '정말 탈퇴할까요?',
  WITHDRAW_CONFIRM_DATA: '지금까지 진단한 모든 상품과 진단 결과',
  WITHDRAW_DONE: '탈퇴가 완료되었습니다. 그동안 팔기전에를 이용해주셔서 감사합니다.',
  // 로그인 방식 표시와 이름 글자 수 표시는 소스의 라벨·제한 상수에서 만든다.
  joinedWith: (provider: SocialProvider) => `${SOCIAL_PROVIDER_INFO[provider].label} 계정으로 가입`,
  nameLength: (length: number) => `${length}/${NAME_MAX_LENGTH}`,
}

// 테스트가 MSW 응답의 details[0].message로 직접 넣는 서버 메시지. 화면은 이 값을 그대로 alert로 보여준다.
// (화면 문구가 아니므로 UI가 바뀌어도 바뀌지 않는다. 시나리오 이름만 보고 어떤 응답인지 알 수 있게 모았다.)
export const SERVER_MESSAGES = {
  DIAGNOSIS_REJECTED: '진단할 수 없는 상품입니다.',
  ANSWER_NOT_SAVED: '답변을 저장하지 못했습니다.',
  ALREADY_RETRIED: '이미 재진단을 요청한 상품입니다.',
  PRODUCT_NOT_DELETABLE: '삭제할 수 없는 상품입니다.',
  NAME_TAKEN: '이미 사용 중인 이름입니다.',
  WITHDRAW_BLOCKED: '진행 중인 진단이 있어 탈퇴할 수 없습니다.',
  REDIAGNOSE_NOT_ALLOWED: '진단을 마친 상품만 다시 진단할 수 있습니다.',
  NOTIFICATION_NOT_SAVED: '알림 설정을 저장하지 못했습니다.',
}
