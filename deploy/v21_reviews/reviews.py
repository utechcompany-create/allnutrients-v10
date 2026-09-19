"""Verified order-item reviews; additive schema, private purchase details."""
from datetime import datetime, timedelta
import io
import warnings
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query, UploadFile, File, Form
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import LargeBinary, String, Integer, Text, Boolean, DateTime, ForeignKey, CheckConstraint, select, func, update, delete, and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, Session
from .db import Base, get_db
from .models import User, Order, OrderItem, Shipment, now
from .security import current_user, require_admin, require_csrf, new_id
from .admin_events import AdminEvent, record, thread_metadata, unread_query

router = APIRouter()


class ProductReview(Base):
    __tablename__ = 'product_reviews'
    __table_args__ = (CheckConstraint('rating >= 1 AND rating <= 5', name='review_rating_range'),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey('order_items.id'), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    product_id: Mapped[str] = mapped_column(String(40), index=True)
    product_name: Mapped[str] = mapped_column(String(200))
    rating: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden_reason: Mapped[str] = mapped_column(String(300), default='')
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    reply: Mapped[str] = mapped_column(Text, default='')
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReviewText(BaseModel):
    rating: int = Field(ge=1, le=5, strict=True)
    content: str = Field(min_length=5, max_length=2000)
    photoIds: list[str] = Field(default_factory=list, max_length=5)

    @field_validator('content')
    @classmethod
    def clean_content(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError('후기는 공백을 제외한 앞뒤 정리 후 5자 이상 입력해 주세요.')
        return value


class CreateReview(ReviewText):
    orderItemId: int = Field(ge=1, strict=True)


class EditReview(ReviewText):
    revision: int = Field(ge=1)


class RevisionIn(BaseModel):
    revision: int = Field(ge=1)


class ReplyIn(RevisionIn):
    content: str = Field(max_length=1000)


class VisibilityIn(RevisionIn):
    hidden: bool
    reason: str = Field(default='', max_length=300)


class ReviewPhoto(Base):
    __tablename__ = 'review_photos'
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey('order_items.id'))
    review_id: Mapped[str | None] = mapped_column(ForeignKey('product_reviews.id'), nullable=True, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    image_data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


@router.post('/api/review-photos', status_code=201)
def upload_photo(request: Request, orderItemId: int = Form(..., ge=1), file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = member(request, db)
    require_csrf(request, db)
    item = db.get(OrderItem, orderItemId)
    order = db.get(Order, item.order_id) if item else None
    if not order or order.user_id != user.id:
        raise HTTPException(404, '구매한 상품을 찾을 수 없습니다.')
    review = db.scalar(select(ProductReview).where(ProductReview.order_item_id == item.id, ProductReview.deleted == False))
    shipment = db.scalar(select(Shipment).where(Shipment.order_id == order.id))
    if not review and not eligible(order, shipment):
        raise HTTPException(409, '배송 완료된 구매 상품에 사진을 첨부할 수 있습니다.')
    raw = file.file.read(10 * 1024 * 1024 + 1)
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, '사진은 한 장당 10MB 이하로 첨부해 주세요.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP') or image.width * image.height > 40_000_000:
                    raise ValueError('unsupported image')
                image.seek(0)
                if image.format == 'JPEG':
                    image.draft('RGB', (1600, 1600))
                normalized = ImageOps.exif_transpose(image)
                normalized.thumbnail((1600, 1600))
                output = io.BytesIO()
                normalized.convert('RGB').save(output, format='JPEG', quality=85)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(400, 'JPG·PNG·WebP 사진만 첨부할 수 있습니다. 사진 파일을 확인해 주세요.')
    db.execute(update(User).where(User.id == user.id).values(name=User.name))
    expired = db.scalars(select(ReviewPhoto).where(ReviewPhoto.user_id == user.id, ReviewPhoto.review_id == None,
                         ReviewPhoto.created_at < now() - timedelta(days=1))).all()
    for old in expired:
        db.delete(old)
    db.flush()
    if db.scalar(select(func.count()).select_from(ReviewPhoto).where(ReviewPhoto.user_id == user.id, ReviewPhoto.review_id == None)) >= 20:
        raise HTTPException(409, '작성 중인 사진이 많습니다. 기존 리뷰를 저장하거나 첨부 사진을 삭제해 주세요.')
    photo = ReviewPhoto(id=new_id('rp'), user_id=user.id, order_item_id=item.id, image_data=output.getvalue())
    db.add(photo)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'id': photo.id, 'url': '/api/review-photos/' + photo.id}


@router.get('/api/review-photos/{photo_id}')
def get_photo(photo_id: str, request: Request, db: Session = Depends(get_db)):
    photo = db.get(ReviewPhoto, photo_id)
    review = db.get(ProductReview, photo.review_id) if photo and photo.review_id else None
    if not photo:
        raise HTTPException(404, '사진을 찾을 수 없습니다.')
    if not review or review.hidden or review.deleted:
        user = current_user(request, db, required=False)
        if not user or (user.id != photo.user_id and user.role != 'admin'):
            raise HTTPException(404, '사진을 찾을 수 없습니다.')
    return Response(photo.image_data, media_type='image/jpeg', headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.delete('/api/review-photos/{photo_id}')
def delete_draft_photo(photo_id: str, request: Request, db: Session = Depends(get_db)):
    user = member(request, db)
    require_csrf(request, db)
    db.execute(update(User).where(User.id == user.id).values(name=User.name))
    photo = db.scalar(select(ReviewPhoto).where(ReviewPhoto.id == photo_id, ReviewPhoto.user_id == user.id, ReviewPhoto.review_id == None))
    if not photo:
        raise HTTPException(404, '작성 중인 사진을 찾을 수 없습니다.')
    db.delete(photo)
    db.commit()
    return {'ok': True}


def attach_photos(db, row, photo_ids):
    if len(set(photo_ids)) != len(photo_ids):
        raise HTTPException(400, '같은 사진을 중복 첨부할 수 없습니다.')
    # Serializes attachment, draft cleanup and deletion for this account.
    db.execute(update(User).where(User.id == row.user_id).values(name=User.name))
    old = db.scalars(select(ReviewPhoto).where(ReviewPhoto.review_id == row.id)).all()
    selected = []
    for photo_id in photo_ids:
        photo = db.get(ReviewPhoto, photo_id)
        if not photo or photo.user_id != row.user_id or photo.order_item_id != row.order_item_id or photo.review_id not in (None, row.id):
            raise HTTPException(400, '첨부할 수 없는 사진입니다. 사진을 다시 선택해 주세요.')
        selected.append(photo)
    changed = [p.id for p in sorted(old, key=lambda p: p.position)] != photo_ids
    for photo in old:
        if photo.id not in photo_ids:
            photo.review_id = None
            photo.created_at = now()
    for position, photo in enumerate(selected):
        photo.review_id, photo.position = row.id, position
    return changed


def member(request, db):
    user = current_user(request, db)
    if user.role == 'admin' or user.id.startswith('guest_'):
        raise HTTPException(403, '구매한 회원 계정에서 리뷰를 작성해 주세요.')
    return user


def eligible(order, shipment):
    return (order.payment_status in ('PAID', 'PARTIAL_REFUNDED', 'REFUNDED')
            and order.order_status != 'CANCELED'
            and (order.order_status in ('DELIVERED', 'COMPLETED', 'EXCHANGED')
                 or (shipment is not None and shipment.status == 'DELIVERED')))


def private(response):
    response.headers['Cache-Control'] = 'private, no-store'


def serialize(row, name, *, db, owner=False):
    # Public responses deliberately exclude order numbers, item/user IDs and full names.
    name = (name or '').strip()
    data = dict(id=row.id, productId=row.product_id, productName=row.product_name,
                author=(name[:1] + '**') if name else '구매자', verifiedPurchase=True,
                rating=row.rating, content=row.content, reply=row.reply,
                createdAt=row.created_at.isoformat(), updatedAt=row.updated_at.isoformat(),
                repliedAt=row.replied_at.isoformat() if row.replied_at else None,
                photos=[{'id': p.id, 'url': '/api/review-photos/' + p.id} for p in db.scalars(
                    select(ReviewPhoto).where(ReviewPhoto.review_id == row.id).order_by(ReviewPhoto.position))])
    if owner:
        data.update(revision=row.revision, hidden=row.hidden, hiddenReason=row.hidden_reason)
    return data


@router.get('/api/reviews')
def public_reviews(response: Response, productId: str = Query(min_length=1, max_length=40),
                   offset: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=50),
                   db: Session = Depends(get_db)):
    private(response)
    visible = (ProductReview.product_id == productId, ProductReview.deleted == False, ProductReview.hidden == False)
    total, average = db.execute(select(func.count(), func.avg(ProductReview.rating)).where(*visible)).one()
    rows = db.execute(select(ProductReview, User.name).join(User, User.id == ProductReview.user_id)
                      .where(*visible).order_by(ProductReview.created_at.desc(), ProductReview.id.desc())
                      .offset(offset).limit(limit)).all()
    return dict(total=total, average=round(float(average), 1) if average is not None else None,
                offset=offset, limit=limit, items=[serialize(row, name, db=db) for row, name in rows])


@router.get('/api/reviews/purchases')
def purchases(request: Request, response: Response, productId: str = Query('', max_length=40),
              offset: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=50),
              db: Session = Depends(get_db)):
    user = member(request, db)
    private(response)
    can_write = and_(Order.payment_status.in_(['PAID', 'PARTIAL_REFUNDED', 'REFUNDED']),
                     Order.order_status != 'CANCELED',
                     or_(Order.order_status.in_(['DELIVERED', 'COMPLETED', 'EXCHANGED']), Shipment.status == 'DELIVERED'))
    query = (select(OrderItem, Order, Shipment, ProductReview).join(Order, Order.id == OrderItem.order_id)
             .outerjoin(Shipment, Shipment.order_id == Order.id)
             .outerjoin(ProductReview, ProductReview.order_item_id == OrderItem.id)
             .where(Order.user_id == user.id, or_(can_write, ProductReview.deleted == False)))
    if productId:
        query = query.where(OrderItem.product_id == productId)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = []
    for item, order, shipment, review in db.execute(query.order_by(Order.created_at.desc(), OrderItem.id.desc()).offset(offset).limit(limit)):
        items.append(dict(orderItemId=item.id, orderNo=order.order_no, productId=item.product_id,
                          productName=item.product_name, quantity=item.quantity,
                          canWrite=bool(eligible(order, shipment)),
                          review=serialize(review, user.name, db=db, owner=True) if review and not review.deleted else None))
    return dict(total=total, offset=offset, limit=limit, items=items)


@router.post('/api/reviews', status_code=201)
def create_review(data: CreateReview, request: Request, response: Response, db: Session = Depends(get_db)):
    user = member(request, db)
    require_csrf(request, db)
    private(response)
    # Lock the user's item, so duplicate submissions cannot create multiple reviews.
    db.execute(update(OrderItem).where(OrderItem.id == data.orderItemId,
               OrderItem.order_id.in_(select(Order.id).where(Order.user_id == user.id)))
               .values(quantity=OrderItem.quantity))
    item = db.get(OrderItem, data.orderItemId)
    order = db.get(Order, item.order_id) if item else None
    if not order or order.user_id != user.id:
        raise HTTPException(404, '구매한 상품을 찾을 수 없습니다.')
    shipment = db.scalar(select(Shipment).where(Shipment.order_id == order.id))
    if not eligible(order, shipment):
        raise HTTPException(409, '결제 및 배송 완료된 상품에 리뷰를 작성할 수 있습니다.')
    row = db.scalar(select(ProductReview).where(ProductReview.order_item_id == item.id))
    if row and not row.deleted:
        raise HTTPException(409, '이미 리뷰를 작성한 상품입니다. 내 리뷰에서 수정해 주세요.')
    if row:
        row.deleted = False
        row.revision += 1
        row.rating, row.content, row.updated_at = data.rating, data.content, now()
        row.reply, row.replied_at = '', None
        # A moderated review cannot bypass its hidden state by deleting and reposting.
    else:
        row = ProductReview(id=new_id('rev'), order_item_id=item.id, user_id=user.id,
                            product_id=item.product_id, product_name=item.product_name,
                            rating=data.rating, content=data.content, revision=1)
        db.add(row)
    try:
        db.flush()
        attach_photos(db, row, data.photoIds)
        record(db, 'reviews', row.id, row.revision)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '이미 리뷰를 작성한 상품입니다. 새로고침해 주세요.')
    return serialize(row, user.name, db=db, owner=True)


def lock_review(db, review_id, revision, user_id=None):
    conditions = [ProductReview.id == review_id, ProductReview.deleted == False]
    if user_id is not None:
        conditions.append(ProductReview.user_id == user_id)
    db.execute(update(ProductReview).where(*conditions).values(revision=ProductReview.revision))
    row = db.scalar(select(ProductReview).where(*conditions).execution_options(populate_existing=True))
    if not row:
        raise HTTPException(404, '리뷰를 찾을 수 없습니다.')
    if row.revision != revision:
        raise HTTPException(409, '리뷰가 변경되었습니다. 새로고침 후 다시 확인해 주세요.')
    return row


@router.put('/api/reviews/{review_id}')
def edit_review(review_id: str, data: EditReview, request: Request, response: Response, db: Session = Depends(get_db)):
    user = member(request, db)
    require_csrf(request, db)
    private(response)
    row = lock_review(db, review_id, data.revision, user.id)
    photos_changed = attach_photos(db, row, data.photoIds)
    if (row.rating, row.content) != (data.rating, data.content) or photos_changed:
        row.rating, row.content, row.updated_at = data.rating, data.content, now()
        row.revision += 1
        record(db, 'reviews', row.id, row.revision)
    db.commit()
    return serialize(row, user.name, db=db, owner=True)


@router.delete('/api/reviews/{review_id}')
def delete_review(review_id: str, data: RevisionIn, request: Request, db: Session = Depends(get_db)):
    user = member(request, db)
    require_csrf(request, db)
    row = lock_review(db, review_id, data.revision, user.id)
    row.deleted, row.content, row.reply, row.updated_at = True, '', '', now()
    photos = db.scalars(select(ReviewPhoto).where(ReviewPhoto.review_id == row.id)).all()
    for photo in photos:
        db.delete(photo)
    db.execute(delete(AdminEvent).where(AdminEvent.kind == 'reviews', AdminEvent.target == row.id))
    db.commit()
    return {'ok': True}


@router.get('/api/admin/reviews')
def admin_reviews(request: Request, response: Response, visibility: Literal['all', 'visible', 'hidden', 'unread'] = 'all',
                  offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50), db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    private(response)
    query = (select(ProductReview, User.name, Order.order_no).join(User, User.id == ProductReview.user_id)
             .join(OrderItem, OrderItem.id == ProductReview.order_item_id).join(Order, Order.id == OrderItem.order_id)
             .where(ProductReview.deleted == False))
    if visibility in ('visible', 'hidden'):
        query = query.where(ProductReview.hidden == (visibility == 'hidden'))
    if visibility == 'unread':
        unread = unread_query(admin.id).where(AdminEvent.kind == 'reviews').subquery()
        query = query.where(ProductReview.id.in_(select(unread.c.target)))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    metadata = thread_metadata(db, admin.id, 'reviews')
    items = []
    for row, name, order_no in db.execute(query.order_by(ProductReview.updated_at.desc(), ProductReview.id.desc()).offset(offset).limit(limit)):
        items.append({**serialize(row, name, db=db, owner=True), 'orderNo': order_no,
                      **metadata.get(row.id, {'unreadCount': 0, 'notificationThrough': 0})})
    return dict(total=total, offset=offset, limit=limit, items=items)


@router.post('/api/admin/reviews/{review_id}/reply')
def reply_review(review_id: str, data: ReplyIn, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    require_csrf(request, db)
    row = lock_review(db, review_id, data.revision)
    row.reply = data.content.strip()
    row.replied_at = now() if row.reply else None
    db.commit()
    return {'ok': True}


@router.patch('/api/admin/reviews/{review_id}/visibility')
def visibility_review(review_id: str, data: VisibilityIn, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    require_csrf(request, db)
    if data.hidden and not data.reason.strip():
        raise HTTPException(400, '숨김 사유를 입력해 주세요.')
    row = lock_review(db, review_id, data.revision)
    row.hidden, row.hidden_reason = data.hidden, data.reason.strip() if data.hidden else ''
    db.commit()
    return {'ok': True}
