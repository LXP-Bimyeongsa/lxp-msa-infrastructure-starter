package com.lcs.payment.infrastructure.pg;

// PG 승인 취소(환불)에 실패했다 (D-39).
//
// 삼키면 DB에는 REFUNDED인데 PG에는 승인이 살아 있는 상태가 남는다.
// 돈이 실제로 돌아가지 않았는데 돌아간 것처럼 기록되는 것이라, 예외를 전파해
// 트랜잭션을 롤백시킨다. 소비가 멱등하므로 재시도되고, 계속 실패하면 DLQ로 간다.
public class PgCancelFailedException extends RuntimeException {

    public PgCancelFailedException(String transactionId, Throwable cause) {
        super("PG 승인 취소 실패: transactionId=" + transactionId, cause);
    }
}
