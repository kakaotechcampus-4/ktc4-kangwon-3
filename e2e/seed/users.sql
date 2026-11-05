-- E2E 테스트 사용자. app이 떠서 스키마(ddl-auto: update)를 만든 뒤 실행한다.
--   docker compose -f e2e/compose.e2e.yml exec -T db psql -U e2e -d beforeselling < e2e/seed/users.sql
-- user_id는 로그인 헬퍼(e2e/fixtures)가 토큰을 만들 때 같은 값을 쓴다.
INSERT INTO users (user_id, name, social_id, social_provider, role, email, created_at, updated_at)
VALUES ('00000000-0000-7000-8000-0000000e2e01', 'E2E 사용자', 'e2e-user-1', 'KAKAO', 'USER', 'e2e@example.com', now(), now())
ON CONFLICT DO NOTHING;
