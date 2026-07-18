package com.lcs.member.infrastructure.grpc;

import com.lcs.member.application.MemberNotFoundException;
import com.lcs.member.application.MemberService;
import com.lcs.member.domain.Member;
import com.lcs.member.grpc.GetMemberRequest;
import com.lcs.member.grpc.GetMemberResponse;
import com.lcs.member.grpc.MemberQueryServiceGrpc;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import org.springframework.stereotype.Component;

@Component
public class MemberQueryGrpcService extends MemberQueryServiceGrpc.MemberQueryServiceImplBase {

    private final MemberService memberService;

    public MemberQueryGrpcService(MemberService memberService) {
        this.memberService = memberService;
    }

    @Override
    public void getMember(GetMemberRequest request, StreamObserver<GetMemberResponse> responseObserver) {
        try {
            Member member = memberService.findById(request.getMemberId());
            responseObserver.onNext(GetMemberResponse.newBuilder()
                    .setMemberId(member.getId())
                    .setEmail(member.getEmail())
                    .setStatus(member.getStatus().name())
                    .setActive(member.isActive())
                    .build());
            responseObserver.onCompleted();
        } catch (MemberNotFoundException e) {
            // NOT_FOUND는 "회원이 없다"는 정상적인 답이다. 장애가 아니므로
            // 호출 측 서킷브레이커가 이걸 실패로 세지 않도록 예외 타입을 구분해야 한다.
            responseObserver.onError(Status.NOT_FOUND
                    .withDescription("member not found: " + request.getMemberId())
                    .asRuntimeException());
        }
    }
}
