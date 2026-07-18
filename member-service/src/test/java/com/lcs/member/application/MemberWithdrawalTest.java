package com.lcs.member.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;

import com.lcs.common.outbox.OutboxMessage;
import com.lcs.common.outbox.OutboxRepository;
import com.lcs.member.domain.Member;
import com.lcs.member.domain.MemberStatus;
import com.lcs.member.infrastructure.keycloak.KeycloakUserClient;
import com.lcs.member.infrastructure.keycloak.KeycloakUserUpdateException;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

// 회원탈퇴 사가의 시작점 검증 (D-31).
// 구독 해지·환불은 subscription/payment 쪽 책임이므로 여기서는
// "탈퇴 상태 전이와 MemberWithdrawn 발행"까지만 본다.
@SpringBootTest
@ActiveProfiles("test")
class MemberWithdrawalTest {

    @Autowired
    private MemberService memberService;

    @Autowired
    private OutboxRepository outboxRepository;

    @MockitoBean
    private KeycloakUserClient keycloakUserClient;

    @Test
    @DisplayName("탈퇴하면 WITHDRAWN 전이와 MemberWithdrawn outbox가 한 트랜잭션으로 기록된다")
    void withdrawWritesOutbox() {
        Member member = register("withdraw@lxp.dev");

        Member withdrawn = memberService.withdraw(member.getId());

        assertThat(withdrawn.getStatus()).isEqualTo(MemberStatus.WITHDRAWN);

        List<OutboxMessage> events = withdrawnEventsOf(member.getId());
        assertThat(events).hasSize(1);

        OutboxMessage event = events.get(0);
        assertThat(event.routingKey()).isEqualTo("member.withdrawn");
        // 릴레이가 아직 돌지 않았으므로 미발행 상태여야 한다.
        assertThat(event.getPublishedAt()).isNull();
    }

    @Test
    @DisplayName("이미 탈퇴한 회원을 다시 탈퇴시켜도 이벤트가 중복 발행되지 않는다")
    void withdrawIsIdempotent() {
        Member member = register("withdraw-twice@lxp.dev");

        memberService.withdraw(member.getId());
        memberService.withdraw(member.getId()); // 재요청 시뮬레이션

        assertThat(withdrawnEventsOf(member.getId())).hasSize(1);
        assertThat(memberService.findById(member.getId()).getStatus())
                .isEqualTo(MemberStatus.WITHDRAWN);
    }

    @Test
    @DisplayName("없는 회원을 탈퇴시키면 MemberNotFoundException")
    void withdrawUnknownMember() {
        assertThatThrownBy(() -> memberService.withdraw(999_999L))
                .isInstanceOf(MemberNotFoundException.class);
    }

    @Test
    @DisplayName("탈퇴 시 Keycloak 계정을 비활성화한다 — 탈퇴 후 토큰을 받지 못하게(D-32)")
    void withdrawDisablesKeycloakAccount() {
        Member member = register("withdraw-disable@lxp.dev");

        memberService.withdraw(member.getId());

        then(keycloakUserClient).should().disableUser("kc-withdraw-disable@lxp.dev");
    }

    @Test
    @DisplayName("Keycloak 비활성화가 실패하면 탈퇴가 롤백된다 — 인증이 열린 채 탈퇴되지 않도록")
    void withdrawRollsBackWhenKeycloakFails() {
        Member member = register("withdraw-kc-fail@lxp.dev");
        willThrow(new KeycloakUserUpdateException("boom", null))
                .given(keycloakUserClient).disableUser(anyString());

        assertThatThrownBy(() -> memberService.withdraw(member.getId()))
                .isInstanceOf(KeycloakUserUpdateException.class);

        // 롤백됐으므로 여전히 정상 회원이고, 탈퇴 이벤트도 남지 않는다.
        assertThat(memberService.findById(member.getId()).getStatus())
                .isEqualTo(MemberStatus.ACTIVE);
        assertThat(withdrawnEventsOf(member.getId())).isEmpty();
    }

    private Member register(String email) {
        given(keycloakUserClient.createUser(anyString(), anyString(), anyLong()))
                .willReturn("kc-" + email);
        return memberService.register(email, "password1234", "탈퇴테스트");
    }

    // 같은 컨텍스트를 공유하는 테스트들이 outbox에 행을 쌓으므로
    // "마지막 행"이 아니라 memberId로 특정한다.
    private List<OutboxMessage> withdrawnEventsOf(Long memberId) {
        return outboxRepository.findAll().stream()
                .filter(m -> "MemberWithdrawn".equals(m.getEventType()))
                .filter(m -> m.getPayload().contains("\"memberId\":" + memberId))
                .toList();
    }
}
