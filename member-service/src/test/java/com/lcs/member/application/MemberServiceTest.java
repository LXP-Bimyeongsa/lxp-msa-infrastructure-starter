package com.lcs.member.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.lcs.member.domain.Member;
import com.lcs.member.domain.MemberStatus;
import com.lcs.member.infrastructure.persistence.MemberRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class MemberServiceTest {

    @Autowired
    private MemberService memberService;

    @Autowired
    private MemberRepository memberRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Test
    @DisplayName("가입하면 비밀번호가 해시로 저장된다")
    void registerHashesPassword() {
        Member member = memberService.register("hash@lxp.dev", "password1234", "홍길동");

        assertThat(member.getId()).isNotNull();
        assertThat(member.getPasswordHash()).isNotEqualTo("password1234");
        assertThat(passwordEncoder.matches("password1234", member.getPasswordHash())).isTrue();
        assertThat(member.getStatus()).isEqualTo(MemberStatus.ACTIVE);
    }

    @Test
    @DisplayName("같은 이메일로 두 번 가입하면 거부된다")
    void rejectsDuplicateEmail() {
        memberService.register("dup@lxp.dev", "password1234", "김철수");

        assertThatThrownBy(() -> memberService.register("dup@lxp.dev", "other12345678", "이영희"))
                .isInstanceOf(DuplicateEmailException.class);
    }

    @Test
    @DisplayName("선검사를 우회해도 DB unique 제약이 중복을 막는다")
    void databaseConstraintBlocksDuplicate() {
        memberRepository.save(Member.register("race@lxp.dev", "hash1", "선착순"));

        // 애플리케이션 선검사(existsByEmail)를 거치지 않고 직접 저장을 시도한다.
        // 동시 요청 상황에서 두 스레드가 모두 선검사를 통과하는 경우와 같다.
        assertThatThrownBy(() ->
                memberRepository.saveAndFlush(Member.register("race@lxp.dev", "hash2", "후발주자")))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("없는 회원을 조회하면 예외가 발생한다")
    void findByIdThrowsWhenMissing() {
        assertThatThrownBy(() -> memberService.findById(999_999L))
                .isInstanceOf(MemberNotFoundException.class);
    }
}
