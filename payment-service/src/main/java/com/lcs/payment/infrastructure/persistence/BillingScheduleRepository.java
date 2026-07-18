package com.lcs.payment.infrastructure.persistence;

import com.lcs.payment.domain.BillingSchedule;
import java.time.Instant;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface BillingScheduleRepository extends JpaRepository<BillingSchedule, Long> {

    List<BillingSchedule> findTop100ByActiveTrueAndNextBillingAtBeforeOrderByNextBillingAtAsc(Instant now);
}
