-- 테스트 유저 1,000명. perf-app이 한 번 떠서 스키마(ddl-auto: update)를 만든 뒤 실행한다.
--   docker exec -i be-db psql -U perf -d beforeselling_perf < seed/seed.sql
-- user_id는 k6(lib/auth.js의 userIdOf)와 같은 규칙: 00000000-0000-7000-8000-{n을 12자리 16진수}
-- AT는 k6가 perf JWT_SECRET으로 직접 만든다(필터는 서명·claim만 검증).

INSERT INTO users (user_id, name, social_id, social_provider, role, email, created_at, updated_at)
SELECT ('00000000-0000-7000-8000-' || lpad(to_hex(n), 12, '0'))::uuid,
       'perf-user-' || n,
       'perf-' || n,
       'KAKAO',
       'USER',
       NULL,
       now(),
       now()
FROM generate_series(1, 1000) AS n
ON CONFLICT DO NOTHING;
