# JAVA Code Convention

## 1. 명명 규칙

변수, 메서드, 클래스 등에는 일관된 명명 규칙을 적용해야 합니다.  
명확하고 의미 있는 이름은 코드를 읽기 쉽게 만들며, 규칙성이 더해지면 팀 전체의 생산성에 도움을 줄 수 있습니다.  
위와 같은 이유로 되도록이면 변수, 메서드, 클래스의 명칭은 의미를 알 수 없는 축약어를 사용하지 않고 풀어서 작성하도록 합니다.

---

### 1-1. Layer 별 메서드

Layer에서 사용되는 메서드 명명 규칙이며 예제는 **“User”** 로 작성합니다.

> **Reference**: [파트너플랫폼 스쿼드 코드 컨벤션](https://oliveyoung.tech/2023-12-05/partner-platform-code-convention/)

| Method | Controller and Service | Repository |
| :--- |:-----------------------| :--- |
| **Data Read** | `getUser`              | `findByUser`<br>`countByUser`<br>`existsByUser` |
| **Data Insert** | `createUser`           | `insertUser` |
| **Data Delete** | `removeUser`           | `deleteUser` |
| **Data Modify** | `modifyUser`           | `updateUser` |
| **Event 발행** | `UserEvent`            | - |

- Controller ~ Service Layer의 메서드 명칭과 Repository Layer의 메서드 명칭을 다르게 작성하여, 비즈니스 로직이 동작하는 메서드인지 저장소에 Access하기 위한 기능을 제공하는 메서드인지 구별할 수 있도록 합니다.
- 참고: 기능을 명확히 설명할 수 있다면 `get`, `create`, `remove`를 사용하지 않아도 됩니다.

```java
// UserController
@PostMapping
public ResponseDto<Users> signInUser(
    @RequestBody UserRequest.SignInUserDto request
) {
    userService.signInUser(request);
    // ...
}

// UserService
public void signInUser(
    UserRequest.SignInUserDto request
) {
    userWriteRepository.insertUser(request);
    // ...
}

// UserWriteRepository
void insertUser(UserRequest.SignInUserDto request);
```

---

### 1-2. Test 규칙

#### 1-2-1. `@DisplayName` Annotation

JUnit 5의 `@DisplayName` 애너테이션을 적극 활용합니다.

- **명사의 나열보다 문장형으로 작성**
    - A이면 B이다.
    - A이면 B가 아니고 C다.
- **"~테스트" 지양하기**
    - ❌ `음료 1개 추가 테스트` : 테스트에 대한 설명이 명확하게 끝나지 않음
    - ⭕ `음료를 1개 추가할 수 있다.` : 설명이 명확하게 끝남
- **테스트 행위에 대한 결과까지 기술하기**
    - ❌ `음료를 추가할 수 있다.`
    - ⭕ `음료를 추가하면 주문 목록에 담긴다.`
- **도메인 용어를 사용하기**
    - 메서드 자체의 관점보다 도메인 정책 관점으로 작성
    - ❌ `특정 시간 이전에 주문을 생성하면 실패한다.`
    - ⭕ `영업 시작 시간 이전에는 주문을 생성할 수 없다.`

#### 1-2-2. BDD 스타일 테스트

- **BDD란?**
    - TDD에서 파생된 개발 방법론
    - 함수 단위의 테스트에 집중하기보다, 시나리오에 기반한 테스트 케이스(TC) 자체에 집중하여 테스트를 진행
    - 개발자가 아닌 사람이 봐도 이해할 수 있을 정도의 추상화 수준(레벨) 권장
    - 테스트 자체가 문서의 역할을 할 수 있도록 작성해야 함을 의미
- **Given / When / Then 구조**
    - **Given (어떤 환경에서)**: 시나리오 진행에 필요한 모든 준비 과정 (객체, 값, 상태 등)
    - **When (어떤 행동을 진행했을 때)**: 시나리오 행동 진행
    - **Then (어떤 상태 변화가 일어난다)**: 시나리오 진행에 대한 결과 명시 및 검증

---

### 1-3. 요청/응답 객체 필드명

#### 1-3-1. 공통 (요청/응답)

- **필드명은 DB에서 사용하는 이름을 기준으로 합니다.**
    - `Ticket` Table: `status` → `status`
    - `Member` Table: `nickname` → `nickname`
- **동일 필드 사용 시 식별자 부여**
    - 요청/응답 객체 내에 동일한 필드를 사용하는 경우, 필드 앞에 식별자(권한 등)를 붙입니다.
    - 예: `Member.nickname` (UI에 사용자와 담당자의 닉네임이 모두 표시되는 경우)  
      → `userNickname`, `managerNickname`
- **PK 네이밍 규칙**
    - PK는 반드시 도메인명을 붙입니다.
    - 외부 DTO 필드: `ticketId` (예: `Ticket.id` → `ticketId`)
    - 내부 엔티티 필드:
      ```java
      class Admin {
          @Id
          @Column(name = "admin_id")
          private Long id;
      }
      ```

#### 1-3-2. 요청 객체 (Request)

- **도메인명 생략**
    - URL에 요청하고자 하는 대상 도메인이 명시되는 경우, 도메인명을 생략합니다. (단, PK는 예외)
    - 예: `POST /api/user/tickets`
      ```json
      {
        "title": "string",  // ticketTitle로 받지 않음
        "content": "string"
      }
      ```
    - 예: `GET /api/user/tickets/{ticketId}`

#### 1-3-3. 응답 객체 (Response)

- **PK 포함 반환**
    - 특정 엔티티의 필드값을 반환하는 경우, 확장성을 고려하여 PK를 함께 반환합니다.
    - *(예: UI상 담당자의 닉네임만 요구되는 경우에도 담당자의 PK를 함께 반환)*
- **중첩 객체 속성명**
    - 중첩된 객체의 속성인 경우, 엔티티 이름을 생략합니다. (단, PK는 예외)
- **리스트 필드명 규칙**
    - List의 경우 필드명: `{도메인명}s` (필드명에 `List` 등 자료형 명시 금지)
- **Data Wrapper 사용**
    - 응답 필드는 `data` 필드 래퍼로 감싸 반환합니다. (추후 필드 추가 시 확장성 고려)

```json
{
  "data": {
    "tickets": [
      {
        "ticketId": 1,
        "title": "티켓 제목 예시"
      }
    ]
  }
}
```

#### 1-3-4. 응답 필드 값

- **Enum 반환 규칙**
    - Enum 값은 자료형 그대로(`Enum.name()`) 반환합니다.
  ```java
  public record TicketExampleResponse(
      Long ticketId,
      TicketStatus status
  ) {}
  ```

#### 1-3-5. 페이지네이션 파라미터 이름

- **페이지 번호**: `page`
- **페이지 크기**: `size`
- **정렬 기준**: `sortType`

---

## 2. 디렉토리 구조 (도메인형)

```text
├─ domains
│  └─ [도메인명]
│     ├─ presentation
│     │  ├─ api
│     │  └─ controller
│     ├─ application
│     │  ├─ dto
│     │  │  ├─ request
│     │  │  └─ response
│     │  ├─ usecase
│     │  └─ mapper
│     ├─ domain
│     │  ├─ entity
│     │  ├─ repository
│     │  └─ service
├─ global
│  ├─ common
│  ├─ exception
│  ├─ config
│  ├─ security
│  ├─ util
│  └─ infra
```

### 1️⃣ domains (하위 개별 도메인 관련 aggregate)

`[도메인명]` (ex. `user`, `ticket` 등)

- **`presentation`**
    - `api`: Swagger 명세용 Interface
    - `controller`: `@RestController` 구현체 (REST API). Usecase를 호출하여 응답을 반환
- **`application`**
    - `dto`: 계층 간 데이터 전송을 위한 객체들 (`request` / `response` 구분)
    - `usecase`: 하나의 행위에 대한 비즈니스 로직을 통합. Service 계층에 의존하여 Service 계층에서 반환된 객체를 변환하는 역할 *(다른 usecase 참조는 가급적 지양)*
    - `mapper`: 객체 간의 변환 로직 (ex. DTO ↔ Entity)
- **`domain`**
    - `entity`: 데이터베이스와 직접적으로 매핑되는 JPA 엔티티 클래스. 영속성 계층에서 사용하는 도메인 객체로, 데이터베이스 테이블과 1:1 매핑되며 DB 관련 필드 및 설정을 포함
    - `repository`: 데이터베이스와의 상호작용을 처리하는 Repository 구현체와 관련된 코드를 포함. 쿼리를 작성하거나 JPA 커스텀 메서드를 추가해 비즈니스 요구사항에 맞는 데이터 접근을 처리
    - `service`: Repository 계층에 의존하며, 여러 가지 비즈니스 로직을 제공

### 2️⃣ global

- **`common`**: 서비스 내 공통 응답, 상수 등
- **`exception`**: 서비스 내 커스텀 에러 표준화
- **`config`**: Configuration 클래스 정의
- **`security`**: Spring Security 관련 설정 및 컴포넌트
- **`util`**: Helper, Parser 등 공통 유틸리티
- **`infra`**: 외부 계층 연동 관련 기능

---

## 3. 커스텀 에러 코드 (⚠️)

- 도메인별로 유사한 에러 코드를 중복 생성하지 않고, `global/common/CommonResponseCode` 단일 공통 Enum을 기준으로 사용합니다.
- 단순 상태 코드는 공통 코드를 재사용하며, 상황별 상세 안내가 필요한 경우 `BaseException` 생성자에 커스텀 메시지를 전달하여 동적으로 오버라이딩합니다.
- **트레일링 콤마(Trailing Comma)**: 새로운 예외 추가 시 Git 변경 내역에 추가된 줄만 깔끔하게 인식되도록 마지막 항목에도 콤마(`,`)를 사용합니다.
- 클라이언트(프론트엔드)에서 특정 에러 코드 기반 분기 처리(예: 토큰 만료 재발급, 닉네임 중복 체크 등)가 반드시 필요한 특수 케이스에 한해서만 도메인별 별도 코드를 추가합니다.

### 3-1. 공통 응답 코드 예시

```java
public enum CommonResponseCode implements BaseResponseCode {

    // 2xx Success
    OK(HttpStatus.OK, "OK", "요청이 성공적으로 처리되었습니다."),
    CREATED(HttpStatus.CREATED, "CREATED", "리소스가 성공적으로 생성되었습니다."),
    ;

    private final HttpStatus status;
    private final String code;
    private final String message;
}
```

### 3-2. 도메인별 커스텀 예외 클래스 예시

```java
public enum FileResponseCode implements BaseResponseCode {
    NOT_SUPPORTED_EXTENSION(HttpStatus.BAD_REQUEST, "FILE-001", "지원되지 않는 파일 확장자입니다."),
    NOT_FOUND_S3_FILE(HttpStatus.NOT_FOUND, "FILE-002", "업로드된 문서가 아닙니다."),
    EXCEED_FILE_SIZE(HttpStatus.BAD_REQUEST, "FILE-003", "파일 크기가 허용 용량을 초과했습니다."),
    ;

    private final HttpStatus status;
    private final String code;
    private final String message;
}
```

#### 에러 코드 필드 명명 규칙

| 필드 | 설명                                                     |
| :--- |:-------------------------------------------------------|
| **`domain`** | 관련 도메인(Entity 단위) 이름                                   |
| **`status`** | 동일한 HTTP Status에 대해 여러 Enum 값이 존재할 경우 Name에 명확한 의미를 명시 |
| **`code`** | 동일 도메인에 대한 Error Code 추가 순서 (예: `001`부터 순차 번호 부여)      |
| **`message`** | `~입니다.` 체로 작성                                          |

### 3-3. 요청 값 검증 (Bean Validation)

- Request DTO 필드에 `jakarta.validation.constraints`(`@NotBlank`, `@Size`, `@Min`, `@Max` 등)를 붙이고, 컨트롤러 파라미터에 `@Valid`를 명시합니다.
- 검증 실패는 별도 에러 코드를 만들 필요 없이 `GlobalExceptionHandler`가 자동으로 `COMMON-002`(`올바르지 않은 요청 형식입니다.`) + `details`(필드별 오류 배열)로 응답합니다.
- 각 필드에 어떤 제약 조건이 걸려있는지는 Swagger 요청 스키마에 자동으로 반영되므로(별도 설정/`@Schema` 불필요), 프론트엔드에는 `/error-codes` 페이지 대신 Swagger UI를 안내합니다. 자세한 응답 형식은 [`/error-codes` 페이지](/error-codes)의 "에러 응답 형식" 섹션을 참고합니다.

```java
public record SignUpRequest(
        @NotBlank
        @Size(min = 2, max = 10)
        String nickname
) {
}
```

```java
@PostMapping
public ResponseEntity<ApiResponse<Void>> signUp(@Valid @RequestBody SignUpRequest request) {
    // ...
}
```

---

## 4. Swagger 명시

운영코드와 API 명세를 분리하기 위해 별도 인터페이스를 정의한 후 컨트롤러에서 해당 인터페이스를 구현하는 방식으로 작성한다.

인터페이스 작성
```java
// AuthApi.java

// Tag : name으로 그룹화, 필요 시 description에 간단한 설명 작성
@Tag(name = "Auth", description = """
        인증 API.
        소셜 로그인 시작은 브라우저에서 `GET /oauth2/authorization/{kakao|naver|google}` 로 이동합니다.
        성공 시 `refresh_token` HttpOnly 쿠키가 설정되고 프론트엔드 콜백 URL로 리다이렉트되며,
        프론트엔드는 이어서 `POST /api/v1/auth/reissue` 로 액세스 토큰을 획득합니다.
        """)
public interface AuthApi {

// 컨트롤러의 메서드 1개마다 인터페이스 메서드 1개를 작성한다.
    @Operation(
            // API를 1줄로 표현
            summary = "액세스 토큰 재발급",
            // 동작 방식 등을 작성
            description = """
                    `refresh_token` 쿠키로 액세스 토큰을 재발급합니다. 리프레시 토큰도 함께 회전되어 새 쿠키로 내려갑니다.
                    이전 리프레시 토큰을 재사용하면 `AUTH-003`이 응답되며, 이 경우 재로그인이 필요합니다.
                    """)
    // API 응답을 작성한다.
    @ApiResponseExplanations(
            // success의 responseClass에는 응답 DTO 클래스를 작성한다.
            success = @ApiSuccessResponseExplanation(responseClass = TokenResponse.class, description = "재발급 성공"),
            // 해당 API에서 예외가 반환되는 경우, 해당 예외들을 작성한다.
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = AuthResponseCode.class, name = "INVALID_REFRESH_TOKEN"),
            }
    )
    // 컨트롤러의 인터페이스. 응답 DTO와 메서드명을 동일하게 작성해준다.
    ResponseEntity<ApiResponse<TokenResponse>> reissueToken(
            // 해당 파라미터는 쿠키로부터 입력을 받기때문에 hidden 설정을 해주었지만, 일반 API에서는 요청 예시에 파라미터가 보여야하므로 설정해주지 않는다. (@Parameter 어노테이션 미작성)
            @Parameter(hidden = true) String refreshToken,
            @Parameter(hidden = true) HttpServletResponse response);
```
- **성공 응답**: `@ApiSuccessResponseExplanation`
  - `responseCode`: 기본값 `CommonResponseCode.OK`. `201 CREATED` 등 다른 성공 코드가 필요하면 명시적으로 지정합니다.
  - `responseClass`: `data` 필드에 들어갈 응답 DTO 클래스. 응답 바디가 없으면 생략합니다(기본값 `EmptyClass`).
  - `description`: Swagger 응답 설명.
- **에러 응답**: `@ApiErrorResponseExplanation` (배열로 여러 개 선언 가능)
  - `exceptionCode`: 에러 코드가 정의된 Enum 클래스 (`CommonResponseCode.class`, `AuthResponseCode.class` 등).
  - `name`: 해당 Enum 상수명. 오타 등으로 존재하지 않는 상수를 참조하면 애플리케이션 기동 시(Swagger 문서 생성 시점) `IllegalArgumentException발생`
  - 같은 HTTP 상태 코드에 원인이 여러 개인 경우(예: 401에 인증 없음/토큰 만료/토큰 무효), `@ApiErrorResponseExplanation`을 여러 개 나열하면 Swagger 응답에 예시가 각각 named example로 함께 표시됩니다.
- **공통 인증 에러(자동 추가)**: `@SecurityRequirements`(빈 값)로 공개 처리하지 않은 모든 API는 전역 `bearerAuth`를 상속하며, 이 경우 `COMMON-004`(인증 없음)/`AUTH-001`(액세스 토큰 만료)/`AUTH-002`(액세스 토큰 무효) 3가지 401 예시가 `ApiErrorResponseHandler`에 의해 자동으로 추가됩니다. 인증이 필요한 API라면 이 3가지를 `@ApiErrorResponseExplanation`으로 직접 선언할 필요가 없습니다.

#### 신규 API/에러 코드 작성 규칙

- 신규 API를 추가할 때는 해당 엔드포인트에서 발생 가능한 예외 중 공통 인증 에러를 제외한 나머지(서비스 로직에서 실제로 던지는 `BaseException`의 응답 코드 기준)를 `@ApiErrorResponseExplanation`으로 빠짐없이 명시합니다. 공통 인증 에러(위 항목 참고)는 자동으로 추가되므로 중복 선언하지 않습니다.
- 신규 도메인 `ResponseCode` Enum을 추가하면 `global/controller/ErrorCodeController`의 그룹 목록에도 함께 등록해야, `/error-codes` 페이지에서 전체 에러 코드가 도메인별로 조회됩니다.
- 커스텀 애너테이션/핸들러 위치: `global/annotation/swagger`(애너테이션), `global/config/swagger`(예시 생성 로직 `ApiSuccessResponseHandler`/`ApiErrorResponseHandler`).

---

## 5. HTTP Status 가이드라인

`HttpStatus`는 아래와 같은 기준에 따라 명확히 설정합니다.  
**아래에 정의된 HttpStatus 외의 임의 코드는 사용하지 않습니다.** (성공 시에는 원칙적으로 `200 OK` 사용)

| HTTP Code | Enum 상수 | 의미 | 발생 예시 |
| :--- | :--- | :--- | :--- |
| **400** | `BAD_REQUEST` | 잘못된 요청이나 문법 오류 | `ticketId`로 빈 문자열 또는 형식에 맞지 않는 값을 요청함 |
| **401** | `UNAUTHORIZED` | 인증되지 않은 접근 | Authorization 헤더 또는 JWT 토큰 없이 요청함 |
| **403** | `FORBIDDEN` | 권한 문제 | 타인이 등록한 티켓에 대해 수정/삭제를 시도함 |
| **404** | `NOT_FOUND` | 존재하지 않는 리소스/객체 | 요청된 ID에 해당하는 티켓 데이터가 DB에 존재하지 않음 |
| **409** | `CONFLICT` | 현재 상태와의 충돌 | 중복된 닉네임으로 가입 요청, 현재 티켓 상태에서 허용되지 않는 상태 전이 작업 시도 |

---

## 6. 트랜잭션(`@Transactional`) 어노테이션

Service 클래스는 대부분 읽기 메서드가 다수이고 쓰기 메서드가 소수인 경우가 많습니다.  
이를 고려해 클래스 레벨에는 `@Transactional(readOnly = true)`를 기본값으로 선언하고, 쓰기가 필요한 메서드에만 개별적으로 `@Transactional`을 오버라이드합니다.

```java
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class UserService {

    private final UserRepository userRepository;

    // 읽기: 클래스 레벨 readOnly = true 를 그대로 사용 (애노테이션 생략)
    public User getUser(final Long userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));
    }

    // 쓰기: 메서드 레벨에서 명시적으로 오버라이드
    @Transactional
    public User getOrCreateUser(...) {
        ...
    }
}
```

- **목적**: 읽기 메서드가 다수인 서비스 클래스에서 애노테이션 반복을 줄이고, 새 읽기 메서드를 추가할 때 `readOnly = true`를 빠뜨릴 위험을 원천 차단합니다. 또한 `readOnly = true`인 트랜잭션은 Hibernate가 flush 모드를 `MANUAL`로 설정해 커밋 시점의 dirty checking을 생략하므로 성능상 이점도 있습니다.

---

## 🔗 Reference

- [HTTP 상태 코드 - HTTP \| MDN](https://developer.mozilla.org/ko/docs/Web/HTTP/Status)