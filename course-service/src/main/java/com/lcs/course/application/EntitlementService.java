package com.lcs.course.application;

import com.lcs.course.domain.SubscriptionEntitlement;
import com.lcs.course.infrastructure.persistence.SubscriptionEntitlementRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * 재생 권한 읽기 모델 (D-36).
 *
 * <p>구독의 진실은 subscription-service에 있다. 여기 있는 것은 이벤트로 따라오는 사본이며,
 * "지금 볼 수 있는가"에만 답한다. 금액·플랜·주기 같은 것은 복제하지 않는다 —
 * 필요 없는 것을 복제하면 그것도 맞춰야 할 상태가 된다.
 */
@Service
public class EntitlementService {

    private static final Logger log = LoggerFactory.getLogger(EntitlementService.class);

    private final SubscriptionEntitlementRepository repository;

    public EntitlementService(SubscriptionEntitlementRepository repository) {
        this.repository = repository;
    }

    public void grant(String subscriptionId, Long memberId) {
        repository.save(SubscriptionEntitlement.active(subscriptionId, memberId));
        log.info("재생 권한 부여: memberId={} subscriptionId={}", memberId, subscriptionId);
    }

    public void revoke(String subscriptionId, Long memberId) {
        repository.save(SubscriptionEntitlement.revoked(subscriptionId, memberId));
        log.info("재생 권한 회수: memberId={} subscriptionId={}", memberId, subscriptionId);
    }

    public boolean canPlay(Long memberId) {
        return repository.existsByMemberIdAndActiveIsTrue(memberId);
    }
}
