package com.lcs.course.domain;

import java.time.Instant;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

/**
 * 구독 상태의 읽기 모델 (D-36).
 *
 * <p>course가 구독을 소유하지는 않는다. subscription이 발행한 이벤트를 소비해
 * "이 회원이 지금 볼 수 있는가"만 답할 수 있는 최소 형태로 복제해 둔다.
 *
 * <p><b>왜 복제하는가</b> — 재생할 때마다 subscription을 동기 호출하면 D-17이 일부러
 * 끊어둔 결합이 되살아난다. 게다가 재생은 구독 생성보다 훨씬 잦은 경로라
 * subscription이 course의 가용성을 좌우하게 된다.
 *
 * <p>대가는 결과적 일관성이다 — 결제 직후 아주 잠깐(릴레이 폴링 + 브로커 지연)
 * 재생이 거부될 수 있다. 그 사이 사용자는 재시도하면 되고,
 * 반대 방향(해지했는데 계속 보임)도 같은 크기의 지연으로 닫힌다.
 */
@Document(collection = "subscription_entitlement")
public class SubscriptionEntitlement {

    // subscriptionId를 _id로 쓴다. 같은 구독에 대한 이벤트가 두 번 와도
    // 문서가 하나만 남으므로 소비가 자연히 멱등해진다.
    @Id
    private String subscriptionId;

    @Indexed
    private Long memberId;

    private boolean active;

    private Instant updatedAt;

    protected SubscriptionEntitlement() {
        // Mongo 전용
    }

    private SubscriptionEntitlement(String subscriptionId, Long memberId, boolean active) {
        this.subscriptionId = subscriptionId;
        this.memberId = memberId;
        this.active = active;
        this.updatedAt = Instant.now();
    }

    public static SubscriptionEntitlement active(String subscriptionId, Long memberId) {
        return new SubscriptionEntitlement(subscriptionId, memberId, true);
    }

    public static SubscriptionEntitlement revoked(String subscriptionId, Long memberId) {
        // 문서를 지우지 않고 active=false로 남긴다.
        // "구독한 적 없음"과 "해지했음"은 다른 사실이고, 나중에 되짚을 일이 생긴다.
        return new SubscriptionEntitlement(subscriptionId, memberId, false);
    }

    public String getSubscriptionId() {
        return subscriptionId;
    }

    public Long getMemberId() {
        return memberId;
    }

    public boolean isActive() {
        return active;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
