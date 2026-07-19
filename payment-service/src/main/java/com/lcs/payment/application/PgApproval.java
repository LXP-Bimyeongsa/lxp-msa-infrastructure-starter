package com.lcs.payment.application;

/**
 * PG 승인 결과 (D-39).
 *
 * @param approved      승인 여부
 * @param transactionId 승인 시 PG 거래 ID. 환불할 때 필요하므로 반드시 저장한다
 * @param declineCode   거절 코드 (승인 시 null)
 * @param retryable     재시도할 가치가 있는 거절인가.
 *                      한도 초과는 며칠 뒤 풀리지만 분실·도난 카드는 백 번 해도 안 된다.
 *                      dunning(D-37)이 이 값을 보고 재시도를 건너뛴다
 */
public record PgApproval(boolean approved, String transactionId, String declineCode, boolean retryable) {

    public static PgApproval approved(String transactionId) {
        return new PgApproval(true, transactionId, null, false);
    }

    public static PgApproval declined(String declineCode, boolean retryable) {
        return new PgApproval(false, null, declineCode, retryable);
    }

    /**
     * 통신 실패 — 승인됐는지 <b>알 수 없는</b> 상태다.
     *
     * <p>재시도 가능으로 둔다. 같은 idempotencyKey로 다시 보내면 PG가
     * 이미 승인된 건이면 그 승인을, 아니면 새 승인을 돌려주므로 안전하다.
     */
    public static PgApproval unreachable() {
        return new PgApproval(false, null, "PG_UNREACHABLE", true);
    }
}
