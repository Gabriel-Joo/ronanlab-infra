# apps/harbor-backup — Harbor DB 백업

Harbor 내부 DB(`harbor-database-0`, PostgreSQL 18.3, local-path 5Gi — 지금 w3)의 `registry` 데이터베이스를 하루 한 번 덤프한다(2026-11-10, 가용성 묶음 1).
petmint MySQL 백업(`apps/petmint/backup/cronjob.yaml`)과 같은 방식이다.

```
app.yaml           ArgoCD Application harbor-backup — 자동 Sync, prune · selfHeal 끔, finalizer 없음
cronjob.yaml       CronJob harbor-db-backup(매일 03:45 KST, pg_dump -Fc) + 호스트 NFS 쓰기 PV/PVC harbor-backup
../../scripts/host-nfs-harbor-backup-setup.sh   호스트 export(sudo, 한 번) — ~/backup/harbor → /srv/nfs/backup/harbor, fsid 105
```

- Harbor 자체는 `platform/harbor`(Helm, ArgoCD 밖)다. 백업 CronJob만 git으로 관리한다
- 파일: 호스트 `~/backup/harbor/harbor-registry-YYYYMMDD-HHMMSS.dump` + `.sha256`. 보존 30일, 최신 7개는 늘 남긴다
- 덤프는 `.part`로 쓰고 `pg_restore -l` 목차에 테이블 데이터가 있어야 이름을 바꾼다 — 실패하면 Job이 실패한다
- **이미지 레이어(`harbor-registry-w3` PVC 30Gi, 2026-11-10 w3로 옮김)는 백업하지 않는다.** DB만 있으면 프로젝트 · robot 계정 · 정책은 돌아오지만 레이어가 없는 태그는 pull이 안 된다 —
  앱 이미지는 앱 리포 커밋에서 Jenkins로 다시 빌드할 수 있다는 것을 전제로 한다
- Harbor를 올리면 `cronjob.yaml`의 이미지 태그(`goharbor/harbor-db`)도 같이 올린다 — pg_dump가 서버보다 낮으면 실패한다

## 수동으로 한 번 뜨기

```bash
kubectl -n harbor create job --from=cronjob/harbor-db-backup harbor-db-backup-manual-$(date +%H%M)
kubectl -n harbor logs -f job/harbor-db-backup-manual-...
```

## 복구

운영 DB를 덮기 전에 **시험 DB에 먼저 넣어 행 수를 본다**(아래 검증 기록과 같은 순서).

```bash
# 0. 호스트에서 파일 확인
cd ~/backup/harbor && sha256sum -c harbor-registry-<날짜>.dump.sha256
# 1. Harbor 쓰기를 멈춘다 — core · jobservice 를 0 으로(registry 는 DB 를 쓰지 않는다)
kubectl -n harbor scale deploy harbor-core harbor-jobservice --replicas=0
# 2. 운영 DB 에 새 이름으로 넣고 확인한 뒤 이름을 바꾼다(옛 DB 는 registry_old 로 남긴다 — 지우지 않는다)
kubectl -n harbor exec -it harbor-database-0 -- createdb -U postgres registry_new
#    덤프는 호스트에 있고 kubectl 은 m-k8s 에 있다 — 호스트에서 흘려 넣는다
cat ~/backup/harbor/harbor-registry-<날짜>.dump | (cd ~/k8s-cluster && vagrant ssh m-k8s -c \
  'kubectl -n harbor exec -i harbor-database-0 -- pg_restore -U postgres -d registry_new --no-owner --exit-on-error')
#    행 수를 옛 DB 와 견준 뒤 이름을 바꾼다(registry 에 붙은 연결이 있으면 RENAME 이 실패한다 — 1번을 확인)
kubectl -n harbor exec -it harbor-database-0 -- psql -U postgres -c 'ALTER DATABASE registry RENAME TO registry_old' -c 'ALTER DATABASE registry_new RENAME TO registry'
# 3. 다시 켠다 — helm 값의 replicas 로
kubectl -n harbor scale deploy harbor-core harbor-jobservice --replicas=1
```

`harbor-database-0` 의 PVC 자체가 없어졌으면(노드 디스크 장애) Helm 이 새 PVC 로 빈 DB 를 만든다 — `registry` 가 차트 init 으로 생긴 뒤 위 2번과 같다.

## 검증 기록 (2026-11-10)

- 호스트 export: `/srv/nfs/backup/harbor 192.168.122.0/24(rw,sync,all_squash,anonuid=1000,…,fsid=105)`, bind mount · fstab 확인
- ArgoCD `harbor-backup` Synced/Healthy, PVC Bound(RWX)
- 수동 Job: `harbor-registry-20261110-185750.dump` 500,480바이트, 테이블 데이터 49개, 호스트에서 `sha256sum -c` OK. 덤프 전후 운영 49개 테이블 행 수 변화 없음
- 복구 시험: 같은 이미지로 **따로 띄운 시험 Pod**(emptyDir, Service 선택자와 다른 라벨)에 `pg_restore --exit-on-error` 0.46초 →
  49개 테이블 행 수가 운영과 모두 같음(총 16,260행 — artifact 246 · tag 246 · project 3 · repository 3 · robot 4 · harbor_user 2),
  `schema_migrations` 180/f · 프로젝트 이름(library · petmint · runshoes) 같음. 시험 Pod · 수동 Job은 지웠다(백업 파일은 남김)
