"""Member-owned shipping addresses, separate from immutable order snapshots."""
import hashlib
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from sqlalchemy import DateTime, ForeignKey, String, select, update, func
from sqlalchemy.orm import Mapped, Session, mapped_column
from .db import Base, get_db
from .models import User, now
from .security import current_user, require_csrf

router = APIRouter()


class ShippingAddress(Base):
    __tablename__ = 'shipping_addresses'
    id: Mapped[str] = mapped_column(String(70), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(30))
    postcode: Mapped[str] = mapped_column(String(20))
    address1: Mapped[str] = mapped_column(String(300))
    address2: Mapped[str] = mapped_column(String(300), default='')
    delivery_memo: Mapped[str] = mapped_column(String(300), default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AddressIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    customerName: str = Field(min_length=1, max_length=100)
    customerPhone: str = Field(min_length=1, max_length=30)
    postcode: str = Field(min_length=1, max_length=20)
    address1: str = Field(min_length=1, max_length=300)
    address2: str = Field(default='', max_length=300)
    deliveryMemo: str = Field(default='', max_length=300)


def member(request, db):
    viewer = current_user(request, db, True)
    if viewer.role not in ('customer', 'admin'):
        raise HTTPException(403, '회원만 배송지를 저장할 수 있습니다.')
    return viewer


def address_dict(row):
    return {'id': row.id, 'customerName': row.name, 'customerPhone': row.phone,
            'postcode': row.postcode, 'address1': row.address1, 'address2': row.address2,
            'deliveryMemo': row.delivery_memo}


def remember(db, user_id, data, *, strict=True):
    # A per-member write lock prevents simultaneous requests from duplicating
    # an address or exceeding the limit, on both SQLite and PostgreSQL.
    db.execute(update(User).where(User.id == user_id).values(name=User.name))
    values = data.model_dump() if hasattr(data, 'model_dump') else data
    try:
        data = AddressIn(**{k: values.get(k, '') for k in AddressIn.model_fields})
    except ValidationError:
        if not strict:
            return None
        raise HTTPException(400, '받는 분, 연락처, 우편번호와 주소를 확인해 주세요.')
    fingerprint = [user_id, data.customerName, ''.join(c for c in data.customerPhone if c.isdigit()),
                   data.postcode, data.address1, data.address2]
    address_id = 'addr_' + hashlib.sha256(json.dumps(fingerprint, ensure_ascii=False).encode()).hexdigest()
    row = db.get(ShippingAddress, address_id)
    if not row:
        count = db.scalar(select(func.count()).select_from(ShippingAddress).where(ShippingAddress.user_id == user_id))
        if count >= 20:
            if not strict:
                return None
            raise HTTPException(409, '배송지는 최대 20개까지 저장할 수 있습니다. 사용하지 않는 배송지를 삭제해 주세요.')
        row = ShippingAddress(id=address_id, user_id=user_id)
        db.add(row)
    row.name = data.customerName
    row.phone = data.customerPhone
    row.postcode = data.postcode
    row.address1 = data.address1
    row.address2 = data.address2
    row.delivery_memo = data.deliveryMemo
    row.updated_at = now()
    return row


@router.get('/api/shipping-addresses')
def list_addresses(request: Request, response: Response, db: Session = Depends(get_db)):
    viewer = member(request, db)
    response.headers['Cache-Control'] = 'private, no-store'
    rows = db.scalars(select(ShippingAddress).where(ShippingAddress.user_id == viewer.id)
                      .order_by(ShippingAddress.updated_at.desc(), ShippingAddress.id)).all()
    return [address_dict(row) for row in rows]


@router.post('/api/shipping-addresses')
def save_address(data: AddressIn, request: Request, response: Response, db: Session = Depends(get_db)):
    viewer = member(request, db)
    require_csrf(request, db)
    row = remember(db, viewer.id, data)
    db.commit()
    response.headers['Cache-Control'] = 'private, no-store'
    return address_dict(row)


@router.delete('/api/shipping-addresses/{address_id}')
def delete_address(address_id: str, request: Request, response: Response, db: Session = Depends(get_db)):
    viewer = member(request, db)
    require_csrf(request, db)
    row = db.scalar(select(ShippingAddress).where(ShippingAddress.id == address_id,
                                                 ShippingAddress.user_id == viewer.id))
    if not row:
        raise HTTPException(404, '저장된 배송지를 찾을 수 없습니다.')
    db.delete(row)
    db.commit()
    response.headers['Cache-Control'] = 'private, no-store'
    return {'ok': True}
