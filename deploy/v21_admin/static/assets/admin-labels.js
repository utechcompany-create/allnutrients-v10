(function () {
  'use strict';
  const payment = {
    PENDING:'결제 대기', READY:'결제 준비', IN_PROGRESS:'결제 진행 중',
    AWAITING_DEPOSIT:'입금 대기', WAITING_FOR_DEPOSIT:'가상계좌 입금 대기',
    PAID:'결제 완료', DONE:'결제 완료', CANCELED:'결제 취소',
    PARTIAL_CANCELED:'부분 결제 취소', REFUND_PENDING:'환불 대기', REFUNDING:'환불 처리 중',
    REFUNDED:'환불 완료', PARTIAL_REFUNDED:'부분 환불 완료',
    EXPIRED:'결제 기한 만료', ABORTED:'결제 실패', FAILED:'결제 실패',
  };
  const order = {
    ORDERED:'주문 접수', PAID:'결제 완료', PREPARING:'배송 준비', SHIPPED:'배송 중',
    DELIVERED:'배송 완료', CANCELED:'주문 취소', RETURNED:'반품 완료',
    PARTIAL_RETURN:'부분 반품', EXCHANGE_IN_PROGRESS:'교환 진행 중', EXCHANGED:'교환 완료',
  };
  const shipping = {PREPARING:'배송 준비', SHIPPED:'배송 중', DELIVERED:'배송 완료', RETURNED:'반품 회수 완료'};
  const method = {
    CASH:'무통장입금', CARD:'신용·체크카드', NAVERPAY:'네이버페이', KAKAOPAY:'카카오페이', TRANSFER:'계좌이체', VIRTUAL_ACCOUNT:'가상계좌',
    EASY_PAY:'간편결제', EASYPAY:'간편결제', MOBILE_PHONE:'휴대폰 결제', CELLPHONE:'휴대폰 결제',
    CULTURE_GIFT_CERTIFICATE:'문화상품권', BOOK_GIFT_CERTIFICATE:'도서문화상품권',
    GAME_GIFT_CERTIFICATE:'게임문화상품권', FOREIGN_EASY_PAY:'해외 간편결제',
  };
  const cancellation = {REQUESTED:'취소 접수', APPROVED:'취소 승인', REJECTED:'취소 거절', CANCELED:'신청 취소'};
  const editableOrders = ['ORDERED','PAID','PREPARING','SHIPPED','DELIVERED','CANCELED'];
  const editableShipping = ['PREPARING','SHIPPED','DELIVERED','RETURNED'];
  const label = map => value => map[value] || value || '미지정';
  const options = (values, current) => current && !values.includes(current) ? [...values, current] : values;
  window.AdminLabels = {
    paymentStatus:label(payment), orderStatus:label(order), shippingStatus:label(shipping),
    paymentMethod:label(method), cancellationStatus:label(cancellation),
    orderOptions:current=>options(editableOrders,current), shippingOptions:current=>options(editableShipping,current),
    editableOrder:value=>editableOrders.includes(value), editableShipping:value=>editableShipping.includes(value),
  };
})();
