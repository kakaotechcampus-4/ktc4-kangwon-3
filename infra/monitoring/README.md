# 개요

Prometheus + Grafana로 API·JVM·호스트 지표를 수집해 확인하는 대시보드

## 구조

```
                         ┌──────────── EC2 ─────────────────────────────────────────────┐
 브라우저 ─ https ─ nginx ─┼─ /grafana/ ─▶ 127.0.0.1:3000  mon-grafana ──▶ mon-prometheus │
                         │                                   │                            │
                         │   be_appnet ◀─────────────────────┤ scrape (15s)              │
                         │     be-server:8081 /actuator/prometheus   (8081은 publish 안 함) │
                         │                                   │                            │
                         │   host network ◀──────────────────┘ host.docker.internal:9100 │
                         │     mon-node-exporter 172.17.0.1:9100    (docker0에만 바인딩)  │
                         └────────────────────────────────────────────────────────────────┘
```

| 컨테이너 | 역할 | mem_limit |
|---|---|---|
| mon-prometheus | 수집·저장(보존 7일 / 최대 1GB) | 384m |
| mon-grafana | 대시보드 (`/grafana/`) | 256m |
| mon-node-exporter | 호스트 CPU·메모리·디스크·네트워크 지표 | 64m |
| mon-cadvisor | 컨테이너별 CPU·메모리·OOM·재시작 | 128m |

- 백엔드 actuator는 포트 8081로 분리돼 있고 호스트에 공개하지 않습니다.
- `be-server`는 Blue-Green 두 컨테이너(`be-server-blue`/`be-server-green`)의 공통 네트워크 alias다. Prometheus는 이 이름을 DNS로 조회(`dns_sd_configs`)해 떠 있는 컨테이너를 각각 별도 instance로 수집하고, 전환 중에는 잠깐 두 개가 보인다. 배포 구조는 `backend/beforeselling/deploy/README.md` 참고.
- 호스트에 publish 하는 포트는 Grafana `127.0.0.1:3000` 하나뿐이다. **보안그룹에 3000/8081/9090/9100을 열지 말 것.**
- node-exporter는 호스트 NIC 트래픽을 보기 위해 host 네트워크로 뜨고, 외부 노출을 막으려고 docker0 게이트웨이(`172.17.0.1`)에만 바인딩한다. Prometheus는 `host.docker.internal`(host-gateway)로 접근한다. ufw를 켠다면 docker 대역 → 9100을 허용해야 한다.

## 파일

```
infra/monitoring/
├── docker-compose.yml
├── .env.example
├── prometheus/
│   └── prometheus.yml          # scrape 대상
└── grafana/
    ├── provisioning/           # 데이터소스(Prometheus)·대시보드 provider
    └── dashboards/service-overview.json
```

## 최초 1회 서버 작업

1. `.env` Secret 등록 — `.env.example` 항목을 채운 `.env`를 Base64로 인코딩해 GitHub Secret `MONITORING_ENV_B64`에 등록한다 (`base64 -i .env | pbcopy`). 배포 때마다 이 값으로 서버 `/home/ubuntu/app/monitoring/.env`를 덮어쓰므로 서버 파일을 직접 고치지 않는다.
2. 배포 순서 — 백엔드 docker compose가 모두 실행된 이후 배포(`be_appnet` 네트워크 필요)

`.env`만 바꿨을 때는 paths 트리거가 걸리지 않으므로 Secret 수정 후 Actions에서 이 워크플로를 수동 실행(`workflow_dispatch`)한다.

## 수집 지표

| 영역 | 대시보드 |
|---|---|
| 가용성 | 수집 대상 UP 수 |
| API | RPS, 상태코드별 요청, p50/p95/p99, 엔드포인트별 p95·5xx |
| JVM·커넥션 풀 | 힙, GC 일시정지, Hikari active/idle/pending |
| 호스트 | CPU·메모리·루트 디스크 사용률, load/코어, CPU 모드별(steal·iowait), 메모리·스왑, PSI, 디스크 I/O, 네트워크 |
| 컨테이너 | 컨테이너별 메모리(mem_limit 대비·사용량), CPU, OOM 발생·재시작 횟수(24h) |

## 로컬에서 검증

```bash
# Prometheus 설정 문법 검사
docker run --rm -v "$PWD/infra/monitoring/prometheus:/etc/prometheus:ro" -w /etc/prometheus \
  --entrypoint promtool prom/prometheus:v3.5.0 check config prometheus.yml

# 스택 기동 (be 스택 없이 띄울 땐 네트워크만 임시로 만든다)
docker network create be_appnet
cd infra/monitoring && GF_ADMIN_PASSWORD=local \
  docker compose -p mon-local up -d
# http://localhost:3000/grafana/  (admin / local)
docker compose -p mon-local down -v && docker network rm be_appnet
```

- node-exporter 바인딩 주소 `172.17.0.1`은 서버 docker0 기본 대역을 전제로 합니다. 서버에서 `ip -4 addr show docker0`이 다르면 compose의 `--web.listen-address`를 맞춰야 합니다.

## 대시보드 수정

`service-overview.json`은 프로비저닝 대상이라 UI에서 저장할 수 없습니다. UI에서 수정한 뒤 *Export → JSON*으로 받아 파일을 덮어써서 커밋하면 됩니다.
