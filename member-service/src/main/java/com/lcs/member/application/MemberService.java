package com.lcs.member.application;

import com.lcs.common.outbox.OutboxWriter;
import com.lcs.member.domain.Member;
import com.lcs.member.infrastructure.keycloak.KeycloakUserClient;
import com.lcs.member.infrastructure.persistence.MemberRepository;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MemberService {

    private static final Logger log = LoggerFactory.getLogger(MemberService.class);
    private static final String AGGREGATE = "Member";

    private final MemberRepository memberRepository;
    private final KeycloakUserClient keycloakUserClient;
    private final OutboxWriter outboxWriter;

    public MemberService(MemberRepository memberRepository,
                         KeycloakUserClient keycloakUserClient,
                         OutboxWriter outboxWriter) {
        this.memberRepository = memberRepository;
        this.keycloakUserClient = keycloakUserClient;
        this.outboxWriter = outboxWriter;
    }

    /**
     * 가입 — Keycloak 사용자 생성과 도메인 프로필 저장이 함께 이뤄져야 한다 (P-10).
     *
     * 두 시스템에 걸친 쓰기라 하나의 트랜잭션으로 묶을 수 없다. 순서를 이렇게 둔다.
     *   1) member 저장 (id 확보)
     *   2) Keycloak 사용자 생성 + member_id 속성 주입
     *   3) keycloakId 연결
     *
     * 2번이 실패하면 트랜잭션이 롤백돼 member 행이 사라진다.
     * 3번이 실패하면 Keycloak 사용자를 보상 삭제한다 — 그대로 두면
     * 로그인은 되는데 프로필이 없는 계정이 남는다.
     */
    @Transactional
    public Member register(String email, String rawPassword, String name) {
        // 애플리케이션 선검사와 DB unique 제약을 모두 둔다.
        // 선검사는 사용자에게 나은 메시지를 주기 위한 것이고,
        // 동시 요청에서의 실제 보장은 DB 제약이 한다.
        if (memberRepository.existsByEmail(email)) {
            throw new DuplicateEmailException(email);
        }

        Member member = memberRepository.saveAndFlush(Member.register(email, name));

        String keycloakId = keycloakUserClient.createUser(email, rawPassword, member.getId());
        try {
            member.linkKeycloakUser(keycloakId);
            memberRepository.saveAndFlush(member);
        } catch (RuntimeException e) {
            // keycloakId를 함께 남긴다 — deleteUser는 실패해도 예외를 삼키므로,
            // 보상까지 실패하면 이 줄이 "어느 Keycloak 사용자를 손으로 지워야 하나"의
            // 유일한 단서가 된다. e를 넘겨 원인(제약 위반인지 플러시 실패인지)도 남긴다.
            log.error("keycloakId 연결 실패 — Keycloak 사용자 보상 삭제: memberId={} email={} keycloakId={}",
                    member.getId(), email, keycloakId, e);
            keycloakUserClient.deleteUser(keycloakId);
            throw e;
        }
        return member;
    }

    /**
     * 탈퇴 — 회원탈퇴 사가의 시작점 (D-31).
     *
     * <p>member_db의 상태 전이와 MemberWithdrawn 이벤트를 한 트랜잭션으로 커밋한다.
     * 이후는 코레오그래피다 — subscription이 구독을 해지하고, 그 SubscriptionCancelled를
     * payment가 소비해 환불한다(D-16). member는 뒷일을 알지 못한다.
     *
     * <p>구독 해지를 여기서 gRPC로 직접 부르지 않는 이유 — 탈퇴가 subscription의
     * 가용성에 묶인다. 구독 서비스가 죽어 있으면 탈퇴 자체가 불가능해진다.
     *
     * <p>이미 탈퇴한 회원이면 이벤트를 다시 발행하지 않는다. 재발행해도 소비 측이
     * 멱등하지만, 굳이 환불 경로를 다시 돌릴 이유가 없다.
     *
     * <p>Keycloak 비활성화를 커밋 전에 부르는 이유 (D-32) — 실패하면 트랜잭션이
     * 롤백돼 탈퇴 자체가 없던 일이 된다. 반대로 커밋 후에 부르면, 실패했을 때
     * "DB상 탈퇴했는데 로그인은 되는" 상태가 남는다. 둘 중에는 전자가 낫다:
     * 탈퇴 실패는 재시도하면 되지만, 인증이 열린 채로 탈퇴된 계정은 조용하다.
     */
    @Transactional
    public Member withdraw(Long memberId) {
        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new MemberNotFoundException(memberId));
        if (member.withdraw()) {
            // keycloakId가 없는 회원은 Keycloak 이관(D-20) 이전에 만들어진 행이다.
            // 끊을 자격증명이 애초에 없으므로 건너뛴다.
            if (member.getKeycloakId() != null) {
                keycloakUserClient.disableUser(member.getKeycloakId());
            } else {
                log.warn("keycloakId 없는 회원 탈퇴 — 계정 비활성화 생략: memberId={}", memberId);
            }
            outboxWriter.write(AGGREGATE, String.valueOf(member.getId()), "MemberWithdrawn", Map.of(
                    "memberId", member.getId()
            ));
        }
        return member;
    }

    @Transactional(readOnly = true)
    public Member findById(Long id) {
        return memberRepository.findById(id)
                .orElseThrow(() -> new MemberNotFoundException(id));
    }

    @Transactional(readOnly = true)
    public Member findByEmail(String email) {
        return memberRepository.findByEmail(email)
                .orElseThrow(() -> new MemberNotFoundException(email));
    }
}
