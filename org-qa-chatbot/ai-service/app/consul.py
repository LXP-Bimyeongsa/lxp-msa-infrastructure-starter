"""Consul 서비스 등록/해제.

다른 서비스는 spring-cloud-consul이 해준다. config-repo/application.yml 의
설정을 그대로 옮긴다.

  prefer-ip-address: true              -> 컨테이너 IP로 등록
  health-check-path: /actuator/health  -> 같은 경로를 노출한다
  health-check-interval: 10s
  health-check-critical-timeout: 1m    -> DeregisterCriticalServiceAfter

instance-id를 HOSTNAME으로 고정하는 것도 Spring 쪽과 같다. 재기동하면 같은
항목을 덮어써서 등록이 중복되지 않는다.

종료 시 해제를 반드시 해야 한다. 안 하면 죽은 등록이 남아 gateway가 그쪽으로
보내고, critical 판정이 나기까지 1분간 502가 섞인다(P-19에서 실제로 겪은 것).

등록 실패로 기동을 막지는 않는다. Consul이 재기동 중인 상황에 이 서비스까지
죽으면 복구가 더 느려지고, 로그와 직접 호출로 진단할 수 있는 상태로 떠 있는
편이 낫다. 대신 두 가지를 반드시 같이 한다.

  1. 등록 상태를 /actuator/health 에 노출한다. 등록되지 않은 인스턴스는
     gateway를 통해 도달할 수 없으므로 사실상 트래픽을 처리할 수 없다.
     그런데도 UP을 보고하면 거짓이고, 나중에 502만 보고 원인을 엉뚱한 데서 찾는다.
  2. 백그라운드로 재등록을 재시도한다. 재시도가 없으면 기동 시점에 Consul이
     안 떠 있었다는 이유로 영구히 미등록 상태가 된다. 그게 더 큰 문제다.
"""

import asyncio
import logging
import os
import socket

import httpx

log = logging.getLogger(__name__)

_CHECK_INTERVAL = "10s"
_DEREGISTER_AFTER = "1m"
_TIMEOUT = 5.0

# 재시도 간격. Consul이 한참 뒤에 돌아올 수도 있으므로 상한을 두고 무한히 재시도한다.
_RETRY_INITIAL = 2.0
_RETRY_MAX = 30.0
# 등록이 살아 있는지 확인하는 주기. DeregisterCriticalServiceAfter(1분)보다 짧게 둬서
# 등록이 지워졌을 때 1분 안에 알아차린다.
_VERIFY_INTERVAL = 30.0


def local_ip() -> str:
    """컨테이너 IP. prefer-ip-address: true 에 해당한다.

    호스트명으로 등록하면 Consul에 컨테이너명이 들어가고, 그 이름을 풀 수 있는
    것은 같은 도커 네트워크뿐이다. IP로 등록하는 편이 안전하다.
    """
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        # 로컬 개발에서 호스트명이 안 풀리는 경우가 있다.
        return "127.0.0.1"


class ConsulRegistrar:
    def __init__(self, host: str, port: int, service: str, service_port: int):
        self._base = f"http://{host}:{port}"
        self._service = service
        self._service_port = service_port
        # HOSTNAME은 도커가 컨테이너 ID로 채운다. 로컬 실행에서는 머신 이름이 온다.
        self._instance_id = f"{service}-{os.environ.get('HOSTNAME', 'local')}"
        self._registered = False
        self._last_error: str | None = None
        self._task: asyncio.Task | None = None

    @property
    def instance_id(self) -> str:
        return self._instance_id

    @property
    def registered(self) -> bool:
        return self._registered

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def _payload(self, ip: str) -> dict:
        return {
            "ID": self._instance_id,
            "Name": self._service,
            "Address": ip,
            "Port": self._service_port,
            "Tags": ["ai", "python"],
            "Check": {
                "Name": f"{self._service} health",
                "HTTP": f"http://{ip}:{self._service_port}/actuator/health",
                "Interval": _CHECK_INTERVAL,
                # 이만큼 critical이 지속되면 Consul이 등록을 스스로 지운다.
                # 없으면 비정상 종료로 남은 등록이 영영 목록을 오염시킨다.
                "DeregisterCriticalServiceAfter": _DEREGISTER_AFTER,
            },
        }

    async def _try_register(self) -> bool:
        ip = local_ip()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.put(f"{self._base}/v1/agent/service/register",
                                        json=self._payload(ip))
                resp.raise_for_status()
        except Exception as e:
            self._last_error = f"{type(e).__name__}: {e}"
            return False

        self._registered = True
        self._last_error = None
        log.info("Consul 등록 완료: %s at %s:%s", self._instance_id, ip, self._service_port)
        return True

    async def _is_present(self) -> bool | None:
        """Consul에 우리 등록이 아직 있는지 확인한다. None이면 확인 자체가 실패."""
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base}/v1/agent/service/{self._instance_id}")
        except Exception as e:
            self._last_error = f"{type(e).__name__}: {e}"
            return None
        if resp.status_code == 404:
            return False
        return resp.is_success or None

    async def _ensure_loop(self) -> None:
        """등록 상태를 계속 유지한다. 프로세스가 사는 동안 돈다.

        한 번 성공하면 끝내는 것으로 만들었다가 구멍을 발견해 고쳤다.
        DeregisterCriticalServiceAfter(1분) 때문에 헬스체크가 1분간 실패하면
        Consul이 등록을 지운다. 그 뒤 서비스가 회복해도 등록은 돌아오지 않는데,
        플래그만 True로 남아 있으면 헬스는 UP을 보고하면서 실제로는 트래픽을
        받지 못하는 상태가 된다. 조용히 사라지는 쪽이 제일 나쁘다.
        """
        delay = _RETRY_INITIAL
        while True:
            if self._registered:
                # 등록돼 있다고 믿는 동안에도 주기적으로 실재를 확인한다.
                try:
                    await asyncio.sleep(_VERIFY_INTERVAL)
                except asyncio.CancelledError:
                    return
                present = await self._is_present()
                if present is False:
                    log.warning("Consul에서 등록이 사라졌다 — 다시 등록한다 (%s)",
                                self._instance_id)
                    self._registered = False
                    delay = _RETRY_INITIAL
                continue

            log.warning("Consul 미등록 — %.0f초 후 재시도 (%s)", delay, self._last_error)
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return
            if not await self._try_register():
                delay = min(delay * 2, _RETRY_MAX)

    async def start(self) -> None:
        """등록을 시도하고, 등록 상태를 유지하는 백그라운드 루프를 띄운다."""
        await self._try_register()
        self._task = asyncio.create_task(self._ensure_loop(), name="consul-ensure")

    async def stop(self) -> None:
        """재시도를 멈추고 등록을 해제한다.

        재시도 취소를 먼저 한다. 해제 직후에 재시도가 다시 등록해버리면
        죽은 등록이 남는다.
        """
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if not self._registered:
            return
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.put(
                    f"{self._base}/v1/agent/service/deregister/{self._instance_id}")
                resp.raise_for_status()
            log.info("Consul 등록 해제: %s", self._instance_id)
        except Exception as e:
            # 해제 실패는 치명적이지 않다. DeregisterCriticalServiceAfter가 뒤처리한다.
            log.warning("Consul 등록 해제 실패 — critical 판정 후 자동 해제를 기다린다: %s", e)
        finally:
            self._registered = False
