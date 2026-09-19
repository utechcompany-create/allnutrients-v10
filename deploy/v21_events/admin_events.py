"""Durable customer activity and per-administrator read positions."""
import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import String, Integer, ForeignKey, select, func, and_, update
from sqlalchemy.orm import Mapped, Session, mapped_column
from .db import Base, get_db
from .models import User, BoardPost, Inquiry
from .security import require_admin, require_csrf

router = APIRouter()


class AdminEvent(Base):
    __tablename__ = 'admin_customer_events'
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    target: Mapped[str] = mapped_column(String(80), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)


class AdminRead(Base):
    __tablename__ = 'admin_event_reads'
    admin_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    target: Mapped[str] = mapped_column(String(80), primary_key=True)
    through: Mapped[int] = mapped_column(Integer, default=0)


class EventMigration(Base):
    __tablename__ = 'admin_event_migrations'
    name: Mapped[str] = mapped_column(String(40), primary_key=True)


def record(db, kind, target, position):
    db.add(AdminEvent(kind=kind, target=target, position=position))


def backfill(db):
    if db.get(EventMigration, 'initial-v1'):
        return
    from .chat import ChatMessage, ChatRoom
    roles = dict(db.execute(select(User.id, User.role)).all())
    for kind, model in (('board', BoardPost), ('inquiry', Inquiry)):
        for row in db.scalars(select(model)):
            if roles.get(row.user_id) != 'admin':
                db.merge(AdminEvent(kind=kind, target=row.id, position=1))
            try:
                messages = json.loads(row.messages_json or '[]')
            except (ValueError, TypeError):
                messages = []
            for index, message in enumerate(messages):
                if message.get('role') == 'customer':
                    db.merge(AdminEvent(kind=kind, target=row.id, position=index+2))
    rows = db.execute(select(ChatMessage.id, ChatMessage.room_id, ChatRoom.kind)
                      .join(ChatRoom, ChatRoom.id == ChatMessage.room_id)
                      .where(ChatMessage.sender_role != 'admin')).all()
    for position, target, room_kind in rows:
        db.merge(AdminEvent(kind='groupChat' if room_kind == 'GROUP' else 'directChat', target=target, position=position))
    db.add(EventMigration(name='initial-v1'))


def unread_query(admin_id):
    return select(AdminEvent.kind, AdminEvent.target, func.count().label('unread')).outerjoin(
        AdminRead, and_(AdminRead.admin_id == admin_id, AdminRead.kind == AdminEvent.kind,
                        AdminRead.target == AdminEvent.target)
    ).where(AdminEvent.position > func.coalesce(AdminRead.through, 0)).group_by(AdminEvent.kind, AdminEvent.target)


def thread_metadata(db, admin_id, kind):
    pending = {target: count for _, target, count in db.execute(unread_query(admin_id).where(AdminEvent.kind == kind))}
    positions = dict(db.execute(select(AdminEvent.target, func.max(AdminEvent.position))
                               .where(AdminEvent.kind == kind).group_by(AdminEvent.target)).all())
    return {target: {'unreadCount': pending.get(target, 0), 'notificationThrough': position}
            for target, position in positions.items()}


def counts(db, request, admin):
    from .admin_workflow import admin_work_counts
    result = admin_work_counts(request, db)
    totals = dict(groupChat=0, directChat=0, inquiry=0, board=0)
    rooms = {}
    for kind, target, number in db.execute(unread_query(admin.id)):
        totals[kind] += number
        if kind in ('groupChat', 'directChat'):
            rooms[target] = number
    result.update(totals)
    result.update(adminId=admin.id, liveChat=totals['groupChat']+totals['directChat'],
                  communications=totals['inquiry']+totals['board'],
                  returnTotal=result['returns']+result['exchanges'], roomUnread=rooms)
    return result


@router.get('/api/admin/event-counts')
def event_counts(request: Request, response: Response, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    response.headers['Cache-Control'] = 'private, no-store'
    return counts(db, request, admin)


class ReadItem(BaseModel):
    kind: Literal['groupChat', 'directChat', 'inquiry', 'board']
    target: str = Field(min_length=1, max_length=80)
    through: int = Field(ge=1)


class ReadIn(BaseModel):
    adminId: str = Field(min_length=1, max_length=40)
    items: list[ReadItem] = Field(min_length=1, max_length=100)


@router.post('/api/admin/events/read')
def read_events(data: ReadIn, request: Request, response: Response, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    require_csrf(request, db)
    if data.adminId != admin.id:
        raise HTTPException(409, '관리자 계정이 변경되었습니다. 화면을 새로고침해 주세요.')
    # Monotonic across tabs/devices, including out-of-order acknowledgement requests.
    db.execute(update(User).where(User.id == admin.id).values(name=User.name))
    for item in data.items:
        maximum = db.scalar(select(func.max(AdminEvent.position)).where(
            AdminEvent.kind == item.kind, AdminEvent.target == item.target))
        if not maximum or item.through > maximum:
            raise HTTPException(400, '확인한 이벤트의 위치가 올바르지 않습니다.')
        key = (admin.id, item.kind, item.target)
        row = db.get(AdminRead, key)
        if not row:
            row = AdminRead(admin_id=admin.id, kind=item.kind, target=item.target, through=item.through)
            db.add(row)
            db.flush()
        else:
            row.through = max(row.through, item.through)
    db.commit()
    response.headers['Cache-Control'] = 'private, no-store'
    return counts(db, request, admin)
