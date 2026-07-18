package com.lcs.subscription.application;

import com.lcs.common.outbox.OutboxWriter;
import com.lcs.subscription.domain.Subscription;
import com.lcs.subscription.domain.SubscriptionPlan;
import com.lcs.subscription.domain.SubscriptionStatus;
import com.lcs.subscription.infrastructure.persistence.SubscriptionRepository;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class SubscriptionService {

    private static final Logger log = LoggerFactory.getLogger(SubscriptionService.class);
    private static final String AGGREGATE = "Subscription";

    private final SubscriptionRepository subscriptionRepository;
    private final OutboxWriter outboxWriter;
    private final MemberVerifier memberVerifier;

    public SubscriptionService(SubscriptionRepository subscriptionRepository,
                               OutboxWriter outboxWriter,
                               MemberVerifier memberVerifier) {
        this.subscriptionRepository = subscriptionRepository;
        this.outboxWriter = outboxWriter;
        this.memberVerifier = memberVerifier;
    }

    /** 사가 시작점. PENDING 구독 + SubscriptionCreated 이벤트를 한 트랜잭션으로 커밋한다. */
    @Transactional
    public Subscription subscribe(Long memberId, SubscriptionPlan plan) {
        // 회원 활성 여부를 gRPC로 확인한다(D-17). 확인 불가 시 fail-closed —
        // 트랜잭션이 시작되기 전에 거부해야 유령 구독이 생기지 않는다.
        memberVerifier.verifyActive(memberId);

        Subscription subscription = subscriptionRepository.save(Subscription.request(memberId, plan));
        // 결제에 필요한 데이터를 전부 싣는다(event-carried state transfer, D-17).
        // payment가 구독을 되묻는 동기 호출을 만들지 않기 위함이다.
        outboxWriter.write(AGGREGATE, String.valueOf(subscription.getId()), "SubscriptionCreated", Map.of(
                "subscriptionId", subscription.getId(),
                "memberId", subscription.getMemberId(),
                "plan", subscription.getPlan().name(),
                "amount", subscription.getAmount()
        ));
        return subscription;
    }

    /** 해지. CANCELLED 전이 + SubscriptionCancelled 발행 → payment가 소비해 환불한다(D-16). */
    @Transactional
    public Subscription cancel(Long subscriptionId, Long requesterMemberId) {
        Subscription subscription = findOwned(subscriptionId, requesterMemberId);
        if (subscription.cancel()) {
            outboxWriter.write(AGGREGATE, String.valueOf(subscription.getId()), "SubscriptionCancelled", Map.of(
                    "subscriptionId", subscription.getId(),
                    "memberId", subscription.getMemberId(),
                    "amount", subscription.getAmount()
            ));
        }
        return subscription;
    }

    /** PaymentCompleted 소비. */
    @Transactional
    public void onPaymentCompleted(Long subscriptionId) {
        Subscription subscription = subscriptionRepository.findById(subscriptionId)
                .orElseThrow(() -> new SubscriptionNotFoundException(subscriptionId));
        if (subscription.activate()) {
            // 구독이 실제로 살아난 시점을 알린다 (D-36).
            // SubscriptionCreated는 PENDING 시점이라 "이용 가능"을 뜻하지 않는다 —
            // course가 재생 권한을 판단하려면 활성화 자체가 이벤트여야 한다.
            outboxWriter.write(AGGREGATE, String.valueOf(subscription.getId()), "SubscriptionActivated", Map.of(
                    "subscriptionId", subscription.getId(),
                    "memberId", subscription.getMemberId()
            ));
        } else {
            // 결제 완료 전에 해지된 경우 등. 이미 CANCELLED면 활성화하지 않는다 —
            // 해지 시점에 SubscriptionCancelled가 이미 발행돼 환불 경로가 돈다.
            log.warn("활성화 무시(상태={}): subscriptionId={}", subscription.getStatus(), subscriptionId);
        }
    }

    /** PaymentFailed 소비 — 보상: 구독 취소. */
    @Transactional
    public void onPaymentFailed(Long subscriptionId, String reason) {
        Subscription subscription = subscriptionRepository.findById(subscriptionId)
                .orElseThrow(() -> new SubscriptionNotFoundException(subscriptionId));
        if (subscription.cancel()) {
            log.info("결제 실패 보상으로 구독 취소: subscriptionId={} reason={}", subscriptionId, reason);
            // 결제가 실패했으므로 환불할 것이 없다 — SubscriptionCancelled를 발행하지 않는다.
        }
    }

    /**
     * MemberWithdrawn 소비 — 회원탈퇴 사가 (D-31).
     *
     * <p>살아 있는 구독을 전부 해지하고 각각 SubscriptionCancelled를 발행한다.
     * 그 뒤는 기존 해지 경로와 완전히 같다 — payment가 소비해 환불하고(D-16)
     * 예약된 다음 결제를 취소한다(D-27). 탈퇴 전용 환불 경로를 새로 만들지 않는다.
     *
     * <p>멱등 — cancel()이 이미 CANCELLED인 구독에 false를 돌려주므로 이벤트가
     * 재발행되지 않는다. 같은 MemberWithdrawn이 두 번 와도 환불은 한 번만 돈다.
     *
     * <p>구독이 하나도 없는 회원도 정상이다. 아무것도 하지 않고 끝난다.
     */
    @Transactional
    public void onMemberWithdrawn(Long memberId) {
        List<Subscription> alive =
                subscriptionRepository.findByMemberIdAndStatusNot(memberId, SubscriptionStatus.CANCELLED);
        for (Subscription subscription : alive) {
            if (subscription.cancel()) {
                outboxWriter.write(AGGREGATE, String.valueOf(subscription.getId()), "SubscriptionCancelled", Map.of(
                        "subscriptionId", subscription.getId(),
                        "memberId", subscription.getMemberId(),
                        "amount", subscription.getAmount()
                ));
            }
        }
        log.info("회원탈퇴로 구독 해지: memberId={} 건수={}", memberId, alive.size());
    }

    @Transactional(readOnly = true)
    public Subscription findById(Long subscriptionId) {
        return subscriptionRepository.findById(subscriptionId)
                .orElseThrow(() -> new SubscriptionNotFoundException(subscriptionId));
    }

    private Subscription findOwned(Long subscriptionId, Long memberId) {
        Subscription subscription = subscriptionRepository.findById(subscriptionId)
                .orElseThrow(() -> new SubscriptionNotFoundException(subscriptionId));
        if (!subscription.isOwnedBy(memberId)) {
            // 소유자가 아니면 존재 여부도 숨긴다.
            throw new SubscriptionNotFoundException(subscriptionId);
        }
        return subscription;
    }
}
