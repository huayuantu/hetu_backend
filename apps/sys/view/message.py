from datetime import UTC, datetime

from ninja import Router
from ninja.errors import HttpError

from apps.sys.models import Message, User
from apps.sys.schemas import MessageIn, MessageOut
from apps.sys.utils import AuthBearer
from utils.schema.base import api_schema

router = Router()


def _get_authenticated_user(request):
    auth_info = getattr(request, "auth", None)
    if not auth_info or "id" not in auth_info:
        raise HttpError(401, "用户未认证或会话已过期")
    try:
        return User.objects.get(id=auth_info["id"])
    except User.DoesNotExist as exc:
        raise HttpError(401, "用户未认证或会话已过期") from exc


@router.post("", response=MessageOut, auth=AuthBearer([]))
@api_schema
def send_message(request, payload: MessageIn):
    """发送消息（只需要登录）"""
    sender = _get_authenticated_user(request)

    # 验证接收者是否存在
    try:
        receiver = User.objects.get(id=payload.receiver_id)
    except User.DoesNotExist as exc:
        raise HttpError(404, "接收者不存在") from exc

    # 创建消息
    message = Message.objects.create(
        sender=sender,
        receiver=receiver,
        message_type=payload.message_type,
        subject=payload.subject,
        content=payload.content,
        priority=payload.priority,
        action_url=payload.action_url,
        action_text=payload.action_text,
        status="sent",
    )

    # 返回消息
    return MessageOut(
        id=message.id,
        sender_id=message.sender.id,
        sender_name=message.sender.username,
        sender_nickname=message.sender.nickname,
        receiver_id=message.receiver.id,
        message_type=message.message_type,
        subject=message.subject,
        content=message.content,
        status=message.status,
        priority=message.priority,
        action_url=message.action_url,
        action_text=message.action_text,
        create_time=message.create_time,
        update_time=message.update_time,
        read_time=message.read_time,
    )


@router.get("", response=list[MessageOut], auth=AuthBearer([]))
@api_schema
def get_messages(
    request,
    status: str | None = None,
    message_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """获取当前用户的消息列表（只需要登录）"""
    user = _get_authenticated_user(request)

    # 查询接收者为当前用户的消息
    messages = Message.objects.filter(receiver=user)

    # 状态筛选
    if status:
        messages = messages.filter(status=status)

    # 类型筛选
    if message_type:
        messages = messages.filter(message_type=message_type)

    # 排序和分页
    messages = messages.order_by("-create_time")[offset : offset + limit]

    # 转换为输出格式
    result = []
    for message in messages:
        result.append(
            MessageOut(
                id=message.id,
                sender_id=message.sender.id,
                sender_name=message.sender.username,
                sender_nickname=message.sender.nickname,
                receiver_id=message.receiver.id,
                message_type=message.message_type,
                subject=message.subject,
                content=message.content,
                status=message.status,
                priority=message.priority,
                action_url=message.action_url,
                action_text=message.action_text,
                create_time=message.create_time,
                update_time=message.update_time,
                read_time=message.read_time,
            )
        )

    return result


@router.put("/{message_id}/read", response=MessageOut, auth=AuthBearer([]))
@api_schema
def mark_message_read(request, message_id: int):
    """标记消息为已读（只需要登录）"""
    user = _get_authenticated_user(request)

    try:
        message = Message.objects.get(id=message_id, receiver=user)
    except Message.DoesNotExist as exc:
        raise HttpError(404, "消息不存在") from exc

    # 更新状态
    if message.status != "read":
        message.status = "read"
        message.read_time = datetime.now(UTC)
        message.save()

    # 返回消息
    return MessageOut(
        id=message.id,
        sender_id=message.sender.id,
        sender_name=message.sender.username,
        sender_nickname=message.sender.nickname,
        receiver_id=message.receiver.id,
        message_type=message.message_type,
        subject=message.subject,
        content=message.content,
        status=message.status,
        priority=message.priority,
        action_url=message.action_url,
        action_text=message.action_text,
        create_time=message.create_time,
        update_time=message.update_time,
        read_time=message.read_time,
    )


@router.delete("/{message_id}", response=str, auth=AuthBearer([]))
@api_schema
def delete_message(request, message_id: int):
    """删除消息（只需要登录）"""
    user = _get_authenticated_user(request)

    try:
        message = Message.objects.get(id=message_id, receiver=user)
    except Message.DoesNotExist as exc:
        raise HttpError(404, "消息不存在") from exc

    message.delete()
    return "Ok"


@router.get("/unread-count", response=int, auth=AuthBearer([]))
@api_schema
def get_unread_count(request):
    """获取未读消息数量（只需要登录）"""
    user = _get_authenticated_user(request)

    count = Message.objects.filter(receiver=user, status__in=["sent", "unread"]).count()
    return count

