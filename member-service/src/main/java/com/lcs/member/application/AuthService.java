package com.lcs.member.application;

import com.lcs.member.domain.Member;
import com.lcs.member.infrastructure.jwt.JwtTokenProvider;
import com.lcs.member.infrastructure.persistence.MemberRepository;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {

    private final MemberRepository memberRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider tokenProvider;

    public AuthService(MemberRepository memberRepository,
                       PasswordEncoder passwordEncoder,
                       JwtTokenProvider tokenProvider) {
        this.memberRepository = memberRepository;
        this.passwordEncoder = passwordEncoder;
        this.tokenProvider = tokenProvider;
    }

    @Transactional(readOnly = true)
    public JwtTokenProvider.IssuedToken login(String email, String rawPassword) {
        // 이메일 미존재 / 비밀번호 불일치 / 탈퇴 회원을 같은 예외로 처리한다.
        // 구분해서 응답하면 어떤 이메일이 가입돼 있는지 밖에서 알아낼 수 있다.
        Member member = memberRepository.findByEmail(email)
                .orElseThrow(InvalidCredentialsException::new);

        if (!member.isActive() || !passwordEncoder.matches(rawPassword, member.getPasswordHash())) {
            throw new InvalidCredentialsException();
        }
        return tokenProvider.issue(member.getId(), member.getEmail());
    }
}
