-- perf 전용 role·database 생성. 운영 PG(be-db)에서 운영 superuser로 한 번만 실행한다.
--   docker exec -i be-db psql -U "$DB_USERNAME" -d postgres -v perf_password='<.env.perf의 DB_PASSWORD>' < seed/init-perf-db.sql
-- perf role은 beforeselling_perf의 소유자일 뿐 운영 database의 테이블 권한은 없다.
-- (운영 테이블은 운영 사용자 소유이고 PUBLIC에 SELECT를 주지 않으므로 접속해도 읽을 수 없다.)

CREATE ROLE perf LOGIN PASSWORD :'perf_password';
CREATE DATABASE beforeselling_perf OWNER perf;

-- postgres_exporter가 pg_stat_activity·pg_locks 등 인스턴스 통계를 읽기 위한 조회 전용 권한(데이터 접근 아님)
GRANT pg_monitor TO perf;

-- 정리(프로젝트 종료 시):
--   DROP DATABASE beforeselling_perf;
--   DROP ROLE perf;
