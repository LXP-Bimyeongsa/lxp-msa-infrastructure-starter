package com.lcs.course.infrastructure.persistence;

import com.lcs.course.domain.SubscriptionEntitlement;
import org.springframework.data.mongodb.repository.MongoRepository;

public interface SubscriptionEntitlementRepository extends MongoRepository<SubscriptionEntitlement, String> {

    // 재생 권한 판단의 유일한 질의 (D-36). memberId에 인덱스가 걸려 있다.
    boolean existsByMemberIdAndActiveIsTrue(Long memberId);
}
