# BE Blue-Green 배포

운영 EC2에서 BE 컨테이너 두 개(blue 8080 / green 8082)를 번갈아 띄워 무중단으로 배포합니다. nginx는 `/etc/nginx/be-upstream.conf`가 가리키는 색으로 요청을 보냅니다.

- 스크립트: [`blue-green.sh`](blue-green.sh)
- 테스트: [`test/blue-green.test.sh`](test/blue-green.test.sh) (docker·nginx를 가짜로 바꿔 흐름을 검증. CI에서 실행)
- 호출: [`.github/workflows/backend.yml`](../../../.github/workflows/backend.yml)의 `배포 실행` 단계

## 구성

| 항목 | 값 |
|---|---|
| 컨테이너 | `be-server-blue`(8080), `be-server-green`(8082). 둘 다 네트워크 별칭 `be-server` |
| compose 파일 | `docker-compose.yml` + `docker-compose.prod.yml` |
| 작업 디렉터리 | `/home/ubuntu/app/release` (배포마다 새로 받음) |
| 동시 실행 방지 | `/var/lock/be-deploy.lock` (flock) |

## deploy 흐름

`blue-green.sh deploy <IMAGE_TAG>`

1. nginx가 `be_app` upstream을 쓰는지 확인하고, 지금 서비스 중인 색을 읽습니다.
2. 배포 대상 색이 멈춰 있는지, 가용 메모리가 1,200MB 이상인지 확인합니다.
3. db·redis를 띄웁니다. 이미 떠 있으면 그대로 둡니다.
4. 대상 색을 새 이미지로 띄우고 헬스체크를 기다립니다(최대 180초).
5. `/v3/api-docs`로 스모크 테스트를 합니다(최대 10회).
6. upstream 파일을 대상 색으로 바꾸고 `nginx -t` 후 reload 합니다.
7. 옛 worker가 처리 중인 요청을 마칠 때까지 기다립니다(최대 30초).
8. 옛 색은 지우지 않고 **멈춰 둡니다**. 이 컨테이너가 롤백 대상입니다.

4~6단계에서 실패하면 대상 컨테이너를 지우고 끝납니다. 기존 색이 계속 서비스합니다.

## rollback 흐름

`blue-green.sh rollback`

1. 멈춰 둔 이전 색을 `start` 합니다. `up`을 쓰면 `:latest` 이미지로 새로 만들어지므로 쓰지 않습니다.
2. 헬스체크와 스모크 테스트가 통과하면 nginx를 이전 색으로 전환합니다.
3. 문제가 있던 색은 지웁니다. 남겨 두면 다음 rollback이 문제 버전으로 돌아가기 때문입니다.

## 지켜야 할 상태

- 서비스 중인 색은 하나이고, 다른 색은 "멈춤(직전 정상 버전)" 또는 "없음"입니다.
- 두 색이 동시에 running이면 스크립트가 멈춥니다. nginx upstream 파일과 컨테이너 상태를 직접 확인해야 합니다.

## 수동 롤백

배포 후 `https://palgijeone.com/v3/api-docs` 확인이 실패하면 워크플로가 실패로 끝납니다. 자동 롤백은 없습니다. 필요하면 SSM 세션으로 EC2에 들어가 실행합니다.

```bash
cd /home/ubuntu/app/release
sudo bash blue-green.sh rollback
```

## 처음 설정할 때

- nginx 설정(`infra/nginx`)을 먼저 배포해야 합니다. `be-upstream.conf`가 없으면 deploy가 멈춥니다.
- BE와 AI가 함께 쓰는 `be-ai-net` 네트워크는 워크플로가 없을 때만 만듭니다.
