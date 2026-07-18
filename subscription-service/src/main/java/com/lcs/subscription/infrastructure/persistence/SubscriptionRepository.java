package com.lcs.subscription.infrastructure.persistence;

import com.lcs.subscription.domain.Subscription;
import com.lcs.subscription.domain.SubscriptionStatus;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SubscriptionRepository extends JpaRepository<Subscription, Long> {

    // 회원탈퇴 사가(D-31)에서 살아 있는 구독을 일괄 해지한다.
    // ACTIVE만이 아니라 PENDING(결제 진행 중)도 대상이다 — 탈퇴 직후 결제가 승인되면
    // 주인 없는 ACTIVE 구독이 남는다. 그래서 "CANCELLED가 아닌 전부"로 잡는다.
    List<Subscription> findByMemberIdAndStatusNot(Long memberId, SubscriptionStatus status);
}
