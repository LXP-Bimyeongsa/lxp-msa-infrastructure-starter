package com.lcs.member.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;

import com.lcs.member.domain.Member;
import com.lcs.member.domain.MemberStatus;
import com.lcs.member.infrastructure.keycloak.KeycloakUserClient;
import com.lcs.member.infrastructure.keycloak.KeycloakUserCreationException;
import com.lcs.member.infrastructure.persistence.MemberRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

@SpringBootTest
@ActiveProfiles("test")
class MemberServiceTest {

    @Autowired
    private MemberService memberService;

    @Autowired
    private MemberRepository memberRepository;

    // Keycloak은 외부 시스템이라 모킹한다.
    // 여기서 검증할 것은 "가입 흐름의 순서와 실패 시 보상"이다.
    @MockitoBean
    private KeycloakUserClient keycloakUserClient;

    @Test
    @DisplayName("가입하면 Keycloak 사용자가 만들어지고 프로필에 연결된다")
    void registerCreatesKeycloakUser() {
        given(keycloakUserClient.createUser(anyString(), anyString(), anyLong()))
                .willReturn("kc-uuid-1");

        Member member = memberService.register("kc@lxp.dev", "password1234", "홍길동");

        assertThat(member.getId()).isNotNull();
        assertThat(member.getKeycloakId()).isEqualTo("kc-uuid-1");
        assertThat(member.getStatus()).isEqualTo(MemberStatus.ACTIVE);
        // 내부 memberId가 Keycloak 속성으로 전달돼야 gateway가 클레임으로 받을 수 있다
        then(keycloakUserClient).should().createUser("kc@lxp.dev", "password1234", member.getId());
    }

    @Test
    @DisplayName("Keycloak 생성이 실패하면 프로필도 남지 않는다")
    void keycloakFailureRollsBackProfile() {
        willThrow(new KeycloakUserCreationException("boom", null))
                .given(keycloakUserClient).createUser(anyString(), anyString(), anyLong());

        assertThatThrownBy(() -> memberService.register("fail@lxp.dev", "password1234", "실패"))
                .isInstanceOf(KeycloakUserCreationException.class);

        assertThat(memberRepository.findByEmail("fail@lxp.dev")).isEmpty();
    }

    @Test
    @DisplayName("같은 이메일로 두 번 가입하면 거부된다")
    void rejectsDuplicateEmail() {
        given(keycloakUserClient.createUser(anyString(), anyString(), anyLong()))
                .willReturn("kc-uuid-2");
        memberService.register("dup@lxp.dev", "password1234", "김철수");

        assertThatThrownBy(() -> memberService.register("dup@lxp.dev", "other12345678", "이영희"))
                .isInstanceOf(DuplicateEmailException.class);
    }

    @Test
    @DisplayName("선검사를 우회해도 DB unique 제약이 중복을 막는다")
    void databaseConstraintBlocksDuplicate() {
        memberRepository.save(Member.register("race@lxp.dev", "선착순"));

        assertThatThrownBy(() ->
                memberRepository.saveAndFlush(Member.register("race@lxp.dev", "후발주자")))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("없는 회원을 조회하면 예외가 발생한다")
    void findByIdThrowsWhenMissing() {
        assertThatThrownBy(() -> memberService.findById(999_999L))
                .isInstanceOf(MemberNotFoundException.class);
    }
}
