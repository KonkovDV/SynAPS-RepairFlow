# Как запустить лабораторный образ

Образ ставит RepairFlow из склада колёс. Сети на шаге установки нет. База — Debian bookworm, снимок `python:3.12-slim-bookworm` по дайджесту из `Dockerfile`. Это не Astra Linux и не РЕД ОС: на этих системах образ не гоняли. Склад лежит только в стадии сборки. В готовый образ копируется установленный `/usr/local`.

Склад собирает проверка `wheelhouse`. Локально его кладут в каталог `wheelhouse` рядом с `Dockerfile`, теми же тремя командами, что в этой проверке: скачать колёса по хешам, собрать колесо SynAPS и колесо RepairFlow.

```text
docker pull python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
docker build --pull=false --network none -t repairflow:lab .
docker run --rm --network none --read-only --tmpfs /tmp:rw,mode=1777 repairflow:lab version
```

Демо пишет файлы. Каталог на хосте должен быть доступен пользователю, от которого запущен контейнер. По умолчанию это `nobody`.

```text
docker run --rm --network none --read-only --tmpfs /tmp:rw,mode=1777 -u 65534:65534 -v /path/to/out:/out repairflow:lab demo --out /out
```

Образ не слушает порт, не ходит в 1С и не пишет обратно в учётную систему. Журнал решений и выгрузка CSV остаются командами `repairflow` на смонтированном каталоге. Проверки живости нет: контейнер выполняет одну команду и завершается. Корень при запуске только для чтения. Писать можно в смонтированный каталог результата и во временный `/tmp`.
