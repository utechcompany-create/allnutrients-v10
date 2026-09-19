(function(){
  'use strict';
  const terminal = r => ['REFUNDED','COMPLETED'].includes(r.status);
  const refunded = r => ['COMPLETED','MANUAL_COMPLETED'].includes(r.refundStatus);
  const received = r => !!r.receivedAt && r.receiptConfirmed !== false;
  const completed = r => r.requestType === 'RETURN' && received(r) && terminal(r) && refunded(r) && r.refundCompleted !== false;
  const stopped = r => ['REJECTED','CANCELED'].includes(r.status);
  const needsCheck = r => r.requestType === 'RETURN' && !stopped(r) && !completed(r) && (terminal(r) || refunded(r));
  function refundLabel(r){
    if(stopped(r))return '환불 미진행';
    if(completed(r))return '환불 완료';
    if(!received(r))return '환불 대기 (입고 확인 전)';
    if(needsCheck(r))return '환불 상태 확인 중';
    return r.refundStatus==='MANUAL_PENDING'?'송금 대기':'환불 처리 중';
  }
  function statusLabel(r,fallback){
    if(r.requestType!=='RETURN')return fallback;
    if(completed(r))return '반품·환불 완료';
    if(needsCheck(r))return received(r)?'환불 상태 확인 중':'입고 확인 대기';
    return fallback;
  }
  window.ReturnProgress={received,completed,stopped,needsCheck,refundLabel,statusLabel};
})();
