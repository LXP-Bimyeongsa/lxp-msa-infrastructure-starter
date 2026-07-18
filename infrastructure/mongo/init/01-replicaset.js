// 단일 노드 ReplicaSet 초기화
//
// 노드가 하나여도 ReplicaSet으로 초기화하면 다중 문서 트랜잭션이 동작한다.
// (standalone 모드에서는 트랜잭션 자체가 불가능하다)
// 3노드 구성은 HA 검증 단계에서만 쓴다. (docs/DECISIONS.md D-10)

try {
    rs.status();
    print("ReplicaSet already initialized");
} catch (e) {
    rs.initiate({
        _id: "rs0",
        members: [{ _id: 0, host: "mongo:27017" }]
    });
    print("ReplicaSet rs0 initiated");
}
