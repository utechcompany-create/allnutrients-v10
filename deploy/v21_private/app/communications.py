"""Customer questions with server-enforced private threads."""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import Boolean, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, get_db
from .models import BoardPost, Inquiry, Product
from .security import current_user, new_id, require_admin, require_csrf

router = APIRouter()


class CommunicationPrivacy(Base):
    # An additive table lets existing installations keep their posts and schemas.
    # Missing records mean public, matching the pre-upgrade behavior.
    __tablename__ = 'communication_privacy'
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)


class BoardIn(BaseModel):
    category: str
    title: str
    content: str
    isPrivate: bool = False


class InquiryIn(BaseModel):
    productId: str
    title: str
    content: str
    isPrivate: bool = False


class MessageIn(BaseModel):
    content: str


def no_store(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Vary'] = 'Cookie'


def privacy_flags(db, kind, rows):
    if not rows:
        return {}
    return dict(db.execute(select(CommunicationPrivacy.item_id, CommunicationPrivacy.is_private).where(
        CommunicationPrivacy.kind == kind,
        CommunicationPrivacy.item_id.in_([row.id for row in rows]),
    )).all())


def owns_thread(row, viewer):
    return bool(viewer and (viewer.role == 'admin' or viewer.id == row.user_id))


def serialize(row, kind, viewer, is_private):
    readable = not is_private or owns_thread(row, viewer)
    # Never include hidden content, authors, titles, or replies in an unauthorized
    # response. The browser only receives a placeholder, not a hidden copy.
    messages = []
    if readable:
        try:
            messages = json.loads(row.messages_json or '[]')
        except (TypeError, ValueError):
            messages = []
    out = {
        'id': row.id, 'author': row.author if readable else '비공개',
        'title': row.title if readable else '비밀글입니다.',
        'content': row.content if readable else '', 'messages': messages,
        'status': row.status, 'createdAt': row.created_at.isoformat(),
        'isPrivate': bool(is_private), 'canRead': readable,
        'canFollowup': bool(viewer and readable),
        'canMakePrivate': kind == 'board' and not is_private and owns_thread(row, viewer),
    }
    if kind == 'board':
        out['category'] = row.category if readable or row.category in {'일반문의', '배송문의', '상품후기', '기타'} else '기타'
    else:
        out.update(productId=row.product_id, productName=row.product_name)
    return out


def save_privacy(db, kind, row, is_private):
    if is_private:
        db.add(CommunicationPrivacy(kind=kind, item_id=row.id, is_private=True))


@router.get('/api/board')
def board_list(request: Request, response: Response, db: Session = Depends(get_db)):
    no_store(response)
    viewer = current_user(request, db, False)
    rows = db.scalars(select(BoardPost).order_by(BoardPost.created_at.desc())).all()
    flags = privacy_flags(db, 'board', rows)
    return [serialize(row, 'board', viewer, flags.get(row.id, False)) for row in rows]


@router.post('/api/board')
def board_create(data: BoardIn, request: Request, db: Session = Depends(get_db)):
    require_csrf(request, db)
    user = current_user(request, db, True)
    row = BoardPost(id=new_id('b'), user_id=user.id, author=user.name, category=data.category,
                    title=data.title.strip(), content=data.content.strip(), status='답변대기', messages_json='[]')
    db.add(row)
    save_privacy(db, 'board', row, data.isPrivate)
    db.commit()
    return {'ok': True, 'id': row.id, 'isPrivate': data.isPrivate}


@router.post('/api/board/{post_id}/private')
def board_make_private(post_id: str, request: Request, db: Session = Depends(get_db)):
    require_csrf(request, db)
    viewer = current_user(request, db, True)
    row = db.get(BoardPost, post_id)
    if not row:
        raise HTTPException(404, '게시글을 찾을 수 없습니다.')
    if not owns_thread(row, viewer):
        raise HTTPException(403, '작성자와 관리자만 비밀글로 변경할 수 있습니다.')
    db.merge(CommunicationPrivacy(kind='board', item_id=row.id, is_private=True))
    db.commit()
    return {'ok': True, 'id': row.id, 'isPrivate': True}


@router.get('/api/inquiries')
def inquiry_list(productId: str, request: Request, response: Response, db: Session = Depends(get_db)):
    no_store(response)
    viewer = current_user(request, db, False)
    rows = db.scalars(select(Inquiry).where(Inquiry.product_id == productId).order_by(Inquiry.created_at.desc())).all()
    flags = privacy_flags(db, 'inquiry', rows)
    return [serialize(row, 'inquiry', viewer, flags.get(row.id, False)) for row in rows]


@router.post('/api/inquiries')
def inquiry_create(data: InquiryIn, request: Request, db: Session = Depends(get_db)):
    require_csrf(request, db)
    user = current_user(request, db, True)
    product = db.get(Product, data.productId)
    if not product:
        raise HTTPException(404, '상품을 찾을 수 없습니다.')
    row = Inquiry(id=new_id('q'), product_id=product.id, product_name=product.name,
                  user_id=user.id, author=user.name, title=data.title.strip(), content=data.content.strip(),
                  status='답변대기', messages_json='[]')
    db.add(row)
    save_privacy(db, 'inquiry', row, data.isPrivate)
    db.commit()
    return {'ok': True, 'id': row.id, 'isPrivate': data.isPrivate}


def followup(kind, item_id, data, request, db):
    require_csrf(request, db)
    user = current_user(request, db, True)
    row = db.get(BoardPost if kind == 'board' else Inquiry, item_id)
    if not row:
        raise HTTPException(404, '문의를 찾을 수 없습니다.')
    private = privacy_flags(db, kind, [row]).get(row.id, False)
    if private and not owns_thread(row, user):
        raise HTTPException(403, '비밀글은 작성자와 관리자만 확인하거나 추가 문의를 남길 수 있습니다.')
    try:
        messages = json.loads(row.messages_json or '[]')
    except (TypeError, ValueError):
        messages = []
    messages.append({'role': 'customer', 'author': user.name, 'content': data.content.strip(),
                     'createdAt': datetime.now(timezone.utc).isoformat()})
    row.messages_json = json.dumps(messages, ensure_ascii=False)
    row.status = '답변대기'
    db.commit()
    return {'ok': True}


@router.post('/api/board/{post_id}/followup')
def board_followup(post_id: str, data: MessageIn, request: Request, db: Session = Depends(get_db)):
    return followup('board', post_id, data, request, db)


@router.post('/api/inquiries/{inq_id}/followup')
def inquiry_followup(inq_id: str, data: MessageIn, request: Request, db: Session = Depends(get_db)):
    return followup('inquiry', inq_id, data, request, db)


@router.get('/api/admin/communications')
def admin_comms(request: Request, response: Response, db: Session = Depends(get_db)):
    no_store(response)
    admin = require_admin(request, db)
    out = {}
    for kind, model, key in (('inquiry', Inquiry, 'inquiries'), ('board', BoardPost, 'board')):
        rows = db.scalars(select(model).order_by(model.created_at.desc())).all()
        flags = privacy_flags(db, kind, rows)
        out[key] = [serialize(row, kind, admin, flags.get(row.id, False)) for row in rows]
    return out


@router.post('/api/admin/communications/{kind}/{item_id}/reply')
def admin_reply(kind: str, item_id: str, data: MessageIn, request: Request, db: Session = Depends(get_db)):
    require_csrf(request, db)
    admin = require_admin(request, db)
    model = Inquiry if kind == 'inquiry' else BoardPost if kind == 'board' else None
    row = db.get(model, item_id) if model else None
    if not row:
        raise HTTPException(404, '글을 찾을 수 없습니다.')
    try:
        messages = json.loads(row.messages_json or '[]')
    except (TypeError, ValueError):
        messages = []
    messages.append({'role': 'seller', 'author': admin.name, 'content': data.content.strip(),
                     'createdAt': datetime.now(timezone.utc).isoformat()})
    row.messages_json = json.dumps(messages, ensure_ascii=False)
    row.status = '답변완료'
    db.commit()
    return {'ok': True}
