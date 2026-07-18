package com.lcs.member.application;

public class MemberNotFoundException extends RuntimeException {

    public MemberNotFoundException(Long id) {
        super("회원을 찾을 수 없습니다: id=" + id);
    }

    public MemberNotFoundException(String email) {
        super("회원을 찾을 수 없습니다: email=" + email);
    }
}
