"""Authenticated shared room and customer/admin direct rooms with SSE delivery."""
import asyncio
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column
from starlette.concurrency import run_in_threadpool
from .db import Base, SessionLocal, get_db
from .models import User
from .security import current_user, require_csrf

router = APIRouter()
now = lambda: datetime.now(timezone.utc)


class ChatRoom(Base):
    __tablename__ = 'chat_rooms'
    id: Mapped[str] = mapped_column(String(90), primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), index=True)
    customer_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    __table_args__ = (UniqueConstraint('room_id','sender_id','client_id', name='uq_chat_message_client'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[str] = mapped_column(ForeignKey('chat_rooms.id'), index=True)
    sender_id: Mapped[str] = mapped_column(String(40))
    sender_name: Mapped[str] = mapped_column(String(100))
    sender_role: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    client_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DirectIn(BaseModel):
    customerId: str = ''


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    clientId: str = Field(min_length=1, max_length=64)


def iso(value):
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


def message_dict(message, viewer):
    return {'id':message.id,'roomId':message.room_id,'senderName':message.sender_name,
            'senderRole':message.sender_role,'content':message.body,'createdAt':iso(message.created_at),
            'isMine':message.sender_id == viewer.id}


def room_dict(db, room, viewer):
    customer = db.get(User,room.customer_id) if room.customer_id else None
    label = '전체 대화방' if room.kind == 'GROUP' else ((customer.name+'님') if viewer.role == 'admin' and customer else '관리자 1:1 상담')
    return {'id':room.id,'kind':room.kind,'name':label,'customerId':room.customer_id if viewer.role == 'admin' else None}


def ensure_room(db, room_id, kind, customer_id=None):
    room = db.get(ChatRoom,room_id)
    if not room:
        room = ChatRoom(id=room_id,kind=kind,customer_id=customer_id)
        db.add(room)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            room = db.get(ChatRoom,room_id)
    return room


def permitted_room(db, room_id, viewer):
    room = db.get(ChatRoom,room_id)
    if not room or not viewer or (room.kind == 'DIRECT' and viewer.role != 'admin' and room.customer_id != viewer.id):
        raise HTTPException(404,'대화방을 찾을 수 없거나 접근 권한이 없습니다.')
    return room


def read_messages(db, room_id, after, before=0):
    stmt = select(ChatMessage).where(ChatMessage.room_id == room_id)
    if before:
        stmt = stmt.where(ChatMessage.id < before)
    if after:
        return db.scalars(stmt.where(ChatMessage.id > after).order_by(ChatMessage.id).limit(100)).all()
    return list(reversed(db.scalars(stmt.order_by(ChatMessage.id.desc()).limit(50)).all()))


@router.get('/api/chat/rooms')
def rooms(request: Request, response: Response, db: Session = Depends(get_db)):
    viewer = current_user(request,db,True)
    response.headers['Cache-Control'] = 'private, no-store'
    ensure_room(db,'all','GROUP')
    stmt = select(ChatRoom)
    if viewer.role != 'admin':
        stmt = stmt.where((ChatRoom.kind == 'GROUP') | (ChatRoom.customer_id == viewer.id))
    rows = db.scalars(stmt.order_by(ChatRoom.created_at.desc())).all()
    out = []
    for room in rows:
        item = room_dict(db,room,viewer)
        latest = db.scalar(select(ChatMessage).where(ChatMessage.room_id == room.id).order_by(ChatMessage.id.desc()).limit(1))
        item['lastMessage'] = latest.body[:100] if latest else ''
        item['lastMessageId'] = latest.id if latest else 0
        out.append(item)
    return sorted(out,key=lambda item:item['lastMessageId'],reverse=True)


@router.post('/api/chat/rooms/direct')
def direct_room(data: DirectIn, request: Request, db: Session = Depends(get_db)):
    require_csrf(request,db)
    viewer = current_user(request,db,True)
    customer_id = data.customerId if viewer.role == 'admin' else viewer.id
    if viewer.role != 'admin' and data.customerId and data.customerId != viewer.id:
        raise HTTPException(403,'본인의 1:1 상담방만 만들 수 있습니다.')
    customer = db.get(User,customer_id)
    if not customer or not customer.is_active or customer.role == 'admin':
        raise HTTPException(400,'상담할 고객을 선택해 주세요.')
    room = ensure_room(db,'direct_'+customer_id,'DIRECT',customer_id)
    return room_dict(db,room,viewer)


@router.get('/api/chat/rooms/{room_id}/messages')
def messages(room_id: str, request: Request, response: Response, after: int = 0, before: int = 0, db: Session = Depends(get_db)):
    viewer = current_user(request,db,True)
    room = permitted_room(db,room_id,viewer)
    if after < 0 or before < 0 or (after and before):
        raise HTTPException(400,'메시지 위치가 올바르지 않습니다.')
    response.headers['Cache-Control'] = 'private, no-store'
    batch = read_messages(db,room_id,after,before)
    return {'room':room_dict(db,room,viewer),'messages':[message_dict(m,viewer) for m in batch],
            'hasOlder':not after and len(batch) == 50}


@router.post('/api/chat/rooms/{room_id}/messages')
def send_message(room_id: str, data: MessageIn, request: Request, db: Session = Depends(get_db)):
    require_csrf(request,db)
    viewer = current_user(request,db,True)
    permitted_room(db,room_id,viewer)
    content = data.content.strip()
    if not content:
        raise HTTPException(400,'메시지를 입력해 주세요.')
    # Serialize per-room writes before allocating an ID so cursor delivery cannot
    # skip an earlier message that commits after a concurrent, later message.
    db.execute(update(ChatRoom).where(ChatRoom.id == room_id).values(kind=ChatRoom.kind))
    same = select(ChatMessage).where(ChatMessage.room_id == room_id,ChatMessage.sender_id == viewer.id,ChatMessage.client_id == data.clientId)
    existing = db.scalar(same)
    if existing:
        if existing.body != content:
            raise HTTPException(409,'전송 요청이 변경되었습니다. 다시 전송해 주세요.')
        return message_dict(existing,viewer)
    message = ChatMessage(room_id=room_id,sender_id=viewer.id,sender_name=viewer.name,sender_role=viewer.role,body=content,client_id=data.clientId)
    db.add(message)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        message = db.scalar(same)
        if not message or message.body != content:
            raise HTTPException(409,'메시지 전송을 다시 시도해 주세요.')
    return message_dict(message,viewer)


def stream_update(request,room_id,after):
    with SessionLocal() as db:
        viewer = current_user(request,db,False)
        try:
            permitted_room(db,room_id,viewer)
        except HTTPException:
            return None
        return [message_dict(m,viewer) for m in read_messages(db,room_id,after)]


async def event_stream(request,room_id,after):
    yield 'retry: 1500\nevent: ready\ndata: {}\n\n'
    tick = 0
    while not await request.is_disconnected():
        batch = await run_in_threadpool(stream_update,request,room_id,after)
        if batch is None:
            yield 'event: access-denied\ndata: {}\n\n'
            return
        if batch:
            after = batch[-1]['id']
            yield f'id: {after}\nevent: messages\ndata: {json.dumps(batch,ensure_ascii=False)}\n\n'
        elif tick % 15 == 0:
            yield ': keepalive\n\n'
        tick += 1
        await asyncio.sleep(1)


@router.get('/api/chat/rooms/{room_id}/events')
def events(room_id: str, request: Request, after: int = 0, db: Session = Depends(get_db)):
    viewer = current_user(request,db,True)
    permitted_room(db,room_id,viewer)
    try:
        cursor = max(0,after,int(request.headers.get('last-event-id','0')))
    except ValueError:
        raise HTTPException(400,'메시지 위치가 올바르지 않습니다.')
    # A live stream must not hold a database connection for its entire lifetime.
    db.close()
    return StreamingResponse(event_stream(request,room_id,cursor),media_type='text/event-stream',
        headers={'Cache-Control':'private, no-store','X-Accel-Buffering':'no'})
