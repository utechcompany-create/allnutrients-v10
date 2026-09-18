from pathlib import Path

def rep(path, old, new):
    p=Path(path); s=p.read_text()
    if old not in s:
        raise SystemExit(f'missing patch target: {path}: {old[:120]!r}')
    p.write_text(s.replace(old,new,1))

rep('app/main.py','version="16.0"','version="17.0"')
rep('app/main.py','''class CancelReviewIn(BaseModel):
    approved:bool
    adminNote:str=""
''','''class CancelReviewIn(BaseModel):
    action:str
    adminNote:str=""
''')
rep('app/main.py','return {"ok":True,"version":"16.0"}','return {"ok":True,"version":"17.0"}')
rep('app/main.py','''@app.post("/api/admin/orders/{order_no}/cancel-review")
def admin_cancel_review(order_no:str,data:CancelReviewIn,request:Request,db:Session=Depends(get_db)):
    require_csrf(request,db);require_admin(request,db)
    o=db.scalar(select(Order).options(selectinload(Order.items),selectinload(Order.shipment)).where(Order.order_no==order_no))
    if not o: raise HTTPException(404,"주문을 찾을 수 없습니다.")
    cr=db.get(OrderCancelRequest,o.id)
    if not cr or cr.status!="REQUESTED": raise HTTPException(409,"취소 신청 상태가 아닙니다.")
    if not data.approved:
        cr.status="REJECTED";cr.admin_note=data.adminNote.strip();cr.completed_at=utcnow();db.commit();return {"ok":True}
    ensure_cancelable(o)
    if o.payment_status=="PAID" and o.payment_key:
        try: payments.cancel(o.payment_key,f"{o.order_no} 주문취소",amount=o.total_amount,idem="cancel-"+o.order_no)
        except Exception as e: raise HTTPException(502,"PG 취소 실패: "+str(e))
        o.payment_status="REFUNDED"
    elif o.payment_status=="PAID":
        o.payment_status="REFUND_PENDING"
    else:
        o.payment_status="CANCELED"
    restore_cancel_benefits(db,o);o.order_status="CANCELED"
    cr.status="APPROVED";cr.admin_note=data.adminNote.strip();cr.completed_at=utcnow();db.commit();return {"ok":True,"paymentStatus":o.payment_status}
''','''@app.post("/api/admin/orders/{order_no}/cancel-review")
def admin_cancel_review(order_no:str,data:CancelReviewIn,request:Request,db:Session=Depends(get_db)):
    require_csrf(request,db);require_admin(request,db)
    action=(data.action or "").strip().upper()
    if action not in {"APPROVE","REJECT"}: raise HTTPException(400,"취소 처리방식을 선택해 주세요.")
    o=db.scalar(select(Order).options(selectinload(Order.items),selectinload(Order.shipment)).where(Order.order_no==order_no))
    if not o: raise HTTPException(404,"주문을 찾을 수 없습니다.")
    cr=db.get(OrderCancelRequest,o.id)
    if not cr or cr.status!="REQUESTED": raise HTTPException(409,"취소 신청 상태가 아닙니다.")
    if action=="REJECT":
        cr.status="REJECTED";cr.admin_note=data.adminNote.strip();cr.completed_at=utcnow();db.commit();return {"ok":True,"action":"REJECT","refundAmount":0,"paymentStatus":o.payment_status}
    ensure_cancelable(o)
    refund_amount=max(0,int(o.total_amount or 0))
    if o.payment_status=="PAID" and o.payment_key:
        try: payments.cancel(o.payment_key,f"{o.order_no} 주문취소 전액환불",amount=refund_amount,idem="cancel-full-"+o.order_no)
        except Exception as e: raise HTTPException(502,"PG 전액 취소 실패: "+str(e))
        o.payment_status="REFUNDED"
    elif o.payment_status=="PAID":
        o.payment_status="REFUND_PENDING"
    else:
        o.payment_status="CANCELED"
    restore_cancel_benefits(db,o);o.order_status="CANCELED"
    cr.status="APPROVED";cr.admin_note=data.adminNote.strip();cr.completed_at=utcnow();db.commit()
    return {"ok":True,"action":"APPROVE","refundAmount":refund_amount,"paymentStatus":o.payment_status}
''')

rep('static/admin.html', '''${o.cancelRequest?`<div class="notice" style="margin-top:10px"><b>주문취소 신청 ${esc(o.cancelRequest.status)}</b><br>사유: ${esc(o.cancelRequest.reason||'')}${o.cancelRequest.adminNote?`<br>관리자 메모: ${esc(o.cancelRequest.adminNote)}`:''}${o.cancelRequest.status==='REQUESTED'?`<div class="actions" style="margin-top:8px"><button class="btn primary small" onclick="reviewCancel('${o.orderNo}',true)">취소 승인</button><button class="btn ghost small" onclick="reviewCancel('${o.orderNo}',false)">취소 거절</button></div>`:''}</div>`:''}''', '''${o.cancelRequest?`<div class="notice" style="margin-top:10px"><b>주문취소 신청 ${esc(o.cancelRequest.status)}</b><br>사유: ${esc(o.cancelRequest.reason||'')}<br>결제금액: <b>${money(o.totalAmount)}</b> · 승인 시 <b>전액 환불</b>${o.cancelRequest.adminNote?`<br>관리자 메모: ${esc(o.cancelRequest.adminNote)}`:''}${o.cancelRequest.status==='REQUESTED'?`<div class="grid2" style="margin-top:8px"><label>취소 처리<select id="cancel-action-${o.orderNo}"><option value="">처리 선택</option><option value="APPROVE">취소 승인 · 결제금액 전액 환불</option><option value="REJECT">취소 거절</option></select></label><label>관리자 메모<input id="cancel-note-${o.orderNo}" placeholder="승인 메모 또는 거절 사유"></label></div><div class="actions" style="margin-top:8px"><button class="btn primary small" onclick="reviewCancel('${o.orderNo}')">취소 처리</button></div>`:''}</div>`:''}''')
rep('static/admin.html', '''async function reviewCancel(no,approved){const adminNote=prompt(approved?'취소 승인 메모 (선택)':'취소 거절 사유를 입력하세요.')||'';try{const r=await api('/api/admin/orders/'+no+'/cancel-review',{method:'POST',body:{approved,adminNote}});await loadAll();toast(approved?(r.paymentStatus==='REFUND_PENDING'?'취소 승인됨 · 현금/수동 환불 처리가 필요합니다.':'취소 승인했습니다.'):'취소 신청을 거절했습니다.')}catch(e){toast(e.message)}}''', '''async function reviewCancel(no){const action=document.getElementById('cancel-action-'+no)?.value||'',adminNote=document.getElementById('cancel-note-'+no)?.value||'';if(!action)return toast('취소 처리방식을 선택해 주세요.');if(action==='REJECT'&&!adminNote.trim())return toast('취소 거절 사유를 입력해 주세요.');if(action==='APPROVE'&&!confirm('취소 승인 시 결제금액 전액을 환불 처리합니다. 진행할까요?'))return;try{const r=await api('/api/admin/orders/'+no+'/cancel-review',{method:'POST',body:{action,adminNote}});await loadAll();if(action==='APPROVE')toast(r.paymentStatus==='REFUND_PENDING'?`취소 승인됨 · ${money(r.refundAmount)} 전액 환불 대기입니다.`:`취소 승인 · ${money(r.refundAmount)} 전액 환불 처리했습니다.`);else toast('취소 신청을 거절했습니다.')}catch(e){toast(e.message)}}''')