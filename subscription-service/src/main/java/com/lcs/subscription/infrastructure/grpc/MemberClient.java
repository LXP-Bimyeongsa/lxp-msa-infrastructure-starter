package com.lcs.subscription.infrastructure.grpc;

import com.lcs.member.grpc.GetMemberRequest;
import com.lcs.member.grpc.GetMemberResponse;
import com.lcs.member.grpc.MemberQueryServiceGrpc;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.Status;
import io.grpc.StatusRuntimeException;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.client.ServiceInstance;
import org.springframework.cloud.client.discovery.DiscoveryClient;
import org.springframework.stereotype.Component;

// member-service gRPC 호출. Consul에서 인스턴스를 찾고, gRPC 포트는
// 서비스가 등록한 메타데이터(grpc-port)에서 읽는다.
@Component
public class MemberClient {

    private static final Logger log = LoggerFactory.getLogger(MemberClient.class);

    private final DiscoveryClient discoveryClient;
    private final String serviceId;
    private final long deadlineMs;
    // 채널은 비싸므로 대상 주소별로 재사용한다.
    private final ConcurrentHashMap<String, ManagedChannel> channels = new ConcurrentHashMap<>();

    public MemberClient(DiscoveryClient discoveryClient,
                        @Value("${grpc.client.member-service.service-id:member-service}") String serviceId,
                        @Value("${grpc.client.member-service.deadline-ms:2000}") long deadlineMs) {
        this.discoveryClient = discoveryClient;
        this.serviceId = serviceId;
        this.deadlineMs = deadlineMs;
    }

    /**
     * @return 회원이 활성 상태면 true
     * @throws MemberNotFoundOnRemoteException 회원이 없음 — 장애가 아니라 정상적인 답
     * @throws MemberServiceUnavailableException 통신 실패 — 서킷브레이커가 셀 대상
     */
    public boolean isActiveMember(long memberId) {
        ServiceInstance instance = pickInstance();
        ManagedChannel channel = channelFor(instance);
        try {
            GetMemberResponse response = MemberQueryServiceGrpc.newBlockingStub(channel)
                    // deadline이 없으면 상대가 응답하지 않을 때 스레드가 무한 대기한다.
                    .withDeadlineAfter(deadlineMs, TimeUnit.MILLISECONDS)
                    .getMember(GetMemberRequest.newBuilder().setMemberId(memberId).build());
            return response.getActive();
        } catch (StatusRuntimeException e) {
            if (e.getStatus().getCode() == Status.Code.NOT_FOUND) {
                // "없는 회원"은 정상 응답이다. 서킷브레이커 실패로 세면 안 된다.
                throw new MemberNotFoundOnRemoteException(memberId);
            }
            throw new MemberServiceUnavailableException(
                    "member-service gRPC 호출 실패: " + e.getStatus().getCode(), e);
        }
    }

    private ServiceInstance pickInstance() {
        List<ServiceInstance> instances = discoveryClient.getInstances(serviceId);
        if (instances.isEmpty()) {
            throw new MemberServiceUnavailableException("member-service 인스턴스를 찾을 수 없습니다", null);
        }
        // 인스턴스가 여러 개여도 지금은 첫 번째를 쓴다.
        // 실제 로드밸런싱이 필요해지면 gRPC name resolver로 교체한다.
        return instances.get(0);
    }

    private ManagedChannel channelFor(ServiceInstance instance) {
        String grpcPort = instance.getMetadata().get("grpc-port");
        if (grpcPort == null) {
            throw new MemberServiceUnavailableException(
                    "member-service에 grpc-port 메타데이터가 없습니다", null);
        }
        String target = instance.getHost() + ":" + grpcPort;
        return channels.computeIfAbsent(target, t -> {
            log.info("member-service gRPC 채널 생성: {}", t);
            return ManagedChannelBuilder.forTarget(t).usePlaintext().build();
        });
    }

    @PreDestroy
    public void shutdown() {
        channels.values().forEach(ManagedChannel::shutdown);
    }
}
