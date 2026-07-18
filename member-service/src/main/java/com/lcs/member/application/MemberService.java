package com.lcs.member.application;

import com.lcs.member.domain.Member;
import com.lcs.member.infrastructure.keycloak.KeycloakUserClient;
import com.lcs.member.infrastructure.persistence.MemberRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MemberService {

    private static final Logger log = LoggerFactory.getLogger(MemberService.class);

    private final MemberRepository memberRepository;
    private final KeycloakUserClient keycloakUserClient;

    public MemberService(MemberRepository memberRepository, KeycloakUserClient keycloakUserClient) {
        this.memberRepository = memberRepository;
        this.keycloakUserClient = keycloakUserClient;
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
            log.error("keycloakId 연결 실패 — Keycloak 사용자 보상 삭제: email={}", email);
            keycloakUserClient.deleteUser(keycloakId);
            throw e;
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
