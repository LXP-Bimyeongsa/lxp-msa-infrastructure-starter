package com.lcs.subscription.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.lcs.common.outbox.OutboxMessage;
import com.lcs.common.outbox.OutboxRepository;
import com.lcs.subscription.domain.Subscription;
import com.lcs.subscription.domain.SubscriptionPlan;
import com.lcs.subscription.domain.SubscriptionStatus;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

@SpringBootTest
@ActiveProfiles("test")
class SubscriptionSagaTest {

    @Autowired
    private SubscriptionService subscriptionService;

    @Autowired
    private OutboxRepository outboxRepository;

    // 이 테스트는 사가 상태 전이를 검증한다. 회원 확인은 통과했다고 가정하고,
    // 확인 실패 경로는 MemberVerifierTest에서 따로 다룬다.
    @MockitoBean
    private MemberVerifier memberVerifier;

    @Test
    @DisplayName("구독 생성 시 PENDING 상태와 SubscriptionCreated outbox가 한 트랜잭션으로 기록된다")
    void subscribeWritesOutbox() {
        Subscription subscription = subscriptionService.subscribe(1L, SubscriptionPlan.BASIC);

        assertThat(subscription.getStatus()).isEqualTo(SubscriptionStatus.PENDING);
        assertThat(subscription.getAmount()).isEqualTo(29_000L);

        OutboxMessage event = latestOutbox();
        assertThat(event.getEventType()).isEqualTo("SubscriptionCreated");
        assertThat(event.routingKey()).isEqualTo("subscription.created");
        assertThat(event.getPayload()).contains("\"amount\":29000");
        assertThat(event.getPublishedAt()).isNull();
    }

    @Test
    @DisplayName("PaymentCompleted를 받으면 ACTIVE로 전이한다 — 두 번 받아도 결과가 같다(멱등)")
    void activateIsIdempotent() {
        Subscription subscription = subscriptionService.subscribe(2L, SubscriptionPlan.PREMIUM);

        subscriptionService.onPaymentCompleted(subscription.getId());
        subscriptionService.onPaymentCompleted(subscription.getId()); // 재전송 시뮬레이션

        assertThat(subscriptionService.findById(subscription.getId()).getStatus())
                .isEqualTo(SubscriptionStatus.ACTIVE);
    }

    @Test
    @DisplayName("PaymentFailed를 받으면 보상으로 CANCELLED — 환불 이벤트는 발행하지 않는다")
    void paymentFailedCompensates() {
        Subscription subscription = subscriptionService.subscribe(3L, SubscriptionPlan.BASIC);
        long outboxBefore = outboxRepository.count();

        subscriptionService.onPaymentFailed(subscription.getId(), "test");

        assertThat(subscriptionService.findById(subscription.getId()).getStatus())
                .isEqualTo(SubscriptionStatus.CANCELLED);
        // 결제가 실패했으므로 환불할 것이 없다 — SubscriptionCancelled 미발행
        assertThat(outboxRepository.count()).isEqualTo(outboxBefore);
    }

    @Test
    @DisplayName("해지하면 SubscriptionCancelled가 발행된다 — 환불 사가의 시작점(D-16)")
    void cancelEmitsCancelledEvent() {
        Subscription subscription = subscriptionService.subscribe(4L, SubscriptionPlan.BASIC);
        subscriptionService.onPaymentCompleted(subscription.getId());

        subscriptionService.cancel(subscription.getId(), 4L);

        OutboxMessage event = latestOutbox();
        assertThat(event.getEventType()).isEqualTo("SubscriptionCancelled");
        assertThat(event.routingKey()).isEqualTo("subscription.cancelled");
    }

    @Test
    @DisplayName("남의 구독은 해지할 수 없다 — 존재 여부도 숨긴다")
    void cannotCancelOthersSubscription() {
        Subscription subscription = subscriptionService.subscribe(5L, SubscriptionPlan.BASIC);

        org.assertj.core.api.Assertions.assertThatThrownBy(
                        () -> subscriptionService.cancel(subscription.getId(), 999L))
                .isInstanceOf(SubscriptionNotFoundException.class);
    }

    @Test
    @DisplayName("해지된 구독에 뒤늦게 PaymentCompleted가 와도 ACTIVE로 되살아나지 않는다")
    void lateCompletionDoesNotReviveCancelled() {
        Subscription subscription = subscriptionService.subscribe(6L, SubscriptionPlan.BASIC);
        subscriptionService.cancel(subscription.getId(), 6L); // 결제 완료 전 해지

        subscriptionService.onPaymentCompleted(subscription.getId()); // 뒤늦은 완료

        assertThat(subscriptionService.findById(subscription.getId()).getStatus())
                .isEqualTo(SubscriptionStatus.CANCELLED);
    }

    private OutboxMessage latestOutbox() {
        return outboxRepository.findAll().stream()
                .reduce((first, second) -> second)
                .orElseThrow();
    }
}
