## Flyway 마이그레이션 작성 가이드

DB 스키마가 바뀌는 PR(테이블 생성, 컬럼 추가·변경·삭제, 인덱스, 제약)은 Flyway 마이그레이션 SQL을 함께 작성합니다.

| 프로필 | `ddl-auto` | 스키마를 바꾸는 주체 |
|---|---|---|
| local | `update` | Hibernate (빠른 확인용) |
| prod (운영·perf) | `validate` | Flyway만. 엔티티와 안 맞으면 기동 실패 |
| test (H2) | `create-drop` | Hibernate (Flyway 꺼짐) |

로컬 DB에 컬럼이 이미 생겼어도, 운영에 반영하려면 마이그레이션이 필요합니다.

### 파일 규칙

- 위치: `backend/beforeselling/src/main/resources/db/migration/`
- 이름: `V{n}__{설명}.sql` (예: `V2__add_product_category.sql`). `n`은 develop의 마지막 버전 + 1
- 파일 하나에는 논리적으로 하나의 변경만 담습니다.
- develop에 병합된 파일은 수정하지 않습니다. 체크섬이 바뀌면 기동이 실패합니다. 잘못된 부분은 새 버전으로 고칩니다.
- 같은 번호로 두 PR이 병합되면 충돌이 납니다. 병합 직전에 develop의 최신 번호를 다시 확인합니다.

### enum 값을 추가·삭제할 때

`@Enumerated(EnumType.STRING)` 컬럼에는 Hibernate가 만든 `{테이블}_{컬럼}_check` 제약이 있습니다. enum이 바뀌면 이 제약도 다시 만들어야 INSERT가 실패하지 않습니다.

```sql
-- V2__add_tool_name_battery.sql
ALTER TABLE product_tool_review DROP CONSTRAINT product_tool_review_tool_name_check;
ALTER TABLE product_tool_review ADD CONSTRAINT product_tool_review_tool_name_check
    CHECK (tool_name IN ('CUSTOMS', 'CHILDREN', 'ELECTRICAL', 'RADIO', 'FOOD_DRUG', 'LABEL_AD', 'BATTERY'));
```

같은 enum을 쓰는 다른 테이블(예: `product_progress.tool_name`)도 함께 변경합니다.

### 작성 후 확인

1. `./gradlew integrationTest --tests "*.FlywayMigrationTest"`
   - 빈 PostgreSQL 16에 모든 마이그레이션을 적용한 뒤 `ddl-auto: validate`로 기동합니다.
   - 엔티티만 바꾸고 마이그레이션을 빠뜨리면 여기서 실패합니다. CI(`./gradlew build`)에서도 같은 테스트가 돕니다.
   - Docker가 필요합니다. Docker가 없으면 건너뜁니다.
2. 운영 스키마와 비교가 필요하면 EC2에서 덤프를 떠서 대조합니다.

```bash
docker exec be-db pg_dump -U <DB_USERNAME> -d <DB_NAME> --schema-only --no-owner --no-privileges
```

### 참고

- `V1__init.sql`은 도입 시점의 baseline입니다. 이미 테이블이 있는 DB(운영·perf·각자 로컬)에서는 실행되지 않고 `flyway_schema_history`에 버전 1로만 기록됩니다(`baseline-on-migrate`). 빈 DB에서는 그대로 실행됩니다.
- 적용 이력: `SELECT * FROM flyway_schema_history ORDER BY installed_rank;`
