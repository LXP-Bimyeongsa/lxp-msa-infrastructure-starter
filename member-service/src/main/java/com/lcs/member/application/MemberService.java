package com.lcs.member.application;

import com.lcs.member.domain.Member;
import com.lcs.member.infrastructure.persistence.MemberRepository;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MemberService {

    private final MemberRepository memberRepository;
    private final PasswordEncoder passwordEncoder;

    public MemberService(MemberRepository memberRepository, PasswordEncoder passwordEncoder) {
        this.memberRepository = memberRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Transactional
    public Member register(String email, String rawPassword, String name) {
        // 애플리케이션 선검사와 DB unique 제약을 모두 둔다.
        // 선검사는 사용자에게 나은 메시지를 주기 위한 것이고,
        // 동시 요청에서의 실제 보장은 DB 제약이 한다.
        if (memberRepository.existsByEmail(email)) {
            throw new DuplicateEmailException(email);
        }
        Member member = Member.register(email, passwordEncoder.encode(rawPassword), name);
        return memberRepository.save(member);
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
