package com.lcs.subscription.infrastructure.persistence;

import com.lcs.subscription.domain.Subscription;
import com.lcs.subscription.domain.SubscriptionStatus;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SubscriptionRepository extends JpaRepository<Subscription, Long> {

    // 회원탈퇴 사가에서 활성 구독 일괄 해지에 사용 예정
    List<Subscription> findByMemberIdAndStatus(Long memberId, SubscriptionStatus status);
}
