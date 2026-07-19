package com.lcs.payment.application;

/**
 * PG 연동 경계 (D-39).
 *
 * <p>실제 PG는 사업자등록이 있어야 키를 받는다(P-01). 그때까지는 목이지만,
 * <b>프로세스 안의 if문이 아니라 네트워크 건너편</b>에 둔다 — 타임아웃·거절 코드·
 * 승인번호 보관·환불 호출처럼 실연동에서 터지는 것들이 목에서도 그대로 드러나야 한다.
 *
 * <p>실연동 시 이 인터페이스의 구현만 바꾼다. 도메인은 PG를 모른다.
 */
public interface PaymentGateway {

    /**
     * 승인 요청.
     *
     * <p>{@code idempotencyKey}는 PG에도 그대로 넘긴다. 타임아웃 후 재시도해도
     * PG가 같은 키를 같은 승인으로 처리하므로 이중 청구가 되지 않는다 —
     * 우리 DB의 멱등키(D-26)만으로는 <b>PG 쪽</b> 중복을 막을 수 없다.
     */
    PgApproval approve(String orderId, long amount, String idempotencyKey);

    /**
     * 승인 취소(환불).
     *
     * @param transactionId 승인 시 PG가 준 거래 ID. 이것 없이는 환불할 수 없다.
     */
    void cancel(String transactionId);
}
