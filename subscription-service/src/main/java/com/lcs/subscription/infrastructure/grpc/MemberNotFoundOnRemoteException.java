package com.lcs.subscription.infrastructure.grpc;

// 회원이 존재하지 않음 — 원격 서비스는 정상 동작 중이다.
// 서킷브레이커 집계에서 제외해야 한다(ignoreExceptions).
public class MemberNotFoundOnRemoteException extends RuntimeException {

    public MemberNotFoundOnRemoteException(long memberId) {
        super("존재하지 않는 회원입니다: memberId=" + memberId);
    }
}
