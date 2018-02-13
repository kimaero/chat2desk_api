import logging
from enum import Enum
from functools import partial
from json import JSONDecodeError
from pprint import pformat
from typing import NamedTuple, List

import requests
from requests import RequestException
from retry import retry

log = logging.getLogger(__name__)
demo_token = '938791b995cebbfaebe36dffb96c58'


def non_empty_dict(**kwargs): return {k: v.value if isinstance(v, Enum) else v
                                      for k, v in dict(**kwargs).items()
                                      if v is not None}


def URL(endpoint: str): return f'https://api.chat2desk.com/{endpoint}'


class Chat2DeskException(BaseException):
    pass


class ResponseError(Chat2DeskException):
    pass


class MessageType(Enum):
    def __str__(self): return str(self.value)

    TO_CLIENT = 'to_client'
    FROM_CLIENT = 'from_client'
    AUTOREPLY = 'autoreply'
    SYSTEM = 'system'


class Transport(Enum):
    def __str__(self): return str(self.value)

    WHATSAPP = 'whatsapp'
    VIBER = 'viber'
    VKONTAKTE = 'vkontakte'
    FACEBOOK = 'facebook'
    TELEGRAM = 'telegram'
    SMS = 'sms'


class DialogState(Enum):
    def __str__(self): return str(self.value)

    OPEN = 'open'
    CLOSED = 'closed'


class Coordinates(NamedTuple):
    lat: str
    lon: str


class Sender:
    def __init__(self, id: str = None, phone: int = None, nickname: str = None):
        if (id is None and phone is None) or (id is not None and phone is not None):
            raise Chat2DeskException('Either id or phone must be present, not both nor none')
        self.id = id
        self.phone = phone
        self.nickname = nickname

    def value(self):
        return non_empty_dict(id=self.id, phone=self.phone, nickname=self.nickname)


class Client:
    def __init__(self, token: str = demo_token):
        super(Client, self).__init__()
        self.token = token
        self.get = partial(self._communicate, verb=requests.get)
        self.post = partial(self._communicate, verb=requests.post)
        self.put = partial(self._communicate, verb=requests.put)
        self.delete = partial(self._communicate, verb=requests.delete)

    @retry(RequestException, tries=10, delay=1, jitter=1)
    def _communicate(self, verb, url, **kwargs):
        headers = kwargs.get('headers', {})
        headers.update(dict(Authorization=self.token))
        response = verb(url, headers=headers, **kwargs)
        try:
            response_json = response.json()
            if response_json['status'] == 'error':
                raise ResponseError(f'Error in request: {response_json["message"]} \n{pformat(kwargs)}')
            else:
                return response_json
        except JSONDecodeError:
            log.exception(f'API response is not JSON:\n'
                          f' - code: {response.status_code}\n'
                          f' - headers: {pformat(response.headers)}\n'
                          f' - content: {response.text}')

    def _get__messages(self, message_id: int = None, transport: Transport = None, channel_id: int = None,
                       client_id: int = None, message_type: MessageType = None, dialog_id: int = None,
                       is_read: bool = None, limit: int = None, offset: int = None):
        return self.get(
            url=URL('v1/messages' + (f'/{message_id}' if message_id else '')),
            params=non_empty_dict(transport=transport, channel_id=channel_id, client_id=client_id, type=message_type,
                                  dialog_id=dialog_id, read=is_read, limit=limit, offset=offset)
        )

    def _post__web_hook(self, webhook_url: str):
        return self.post(
            url=URL('v1/companies/web_hook'),
            data=non_empty_dict(url=webhook_url)
        )

    def _post__chat_close_web_hook(self, webhook_url: str):
        return self.post(
            url=URL('v1/companies/chat_close_web_hook'),
            data=non_empty_dict(url=webhook_url)
        )

    def _post__messages(self, client_id: int = None, text: str = None, transport: Transport = None,
                        attachment: str = None, pdf: str = None, message_type: MessageType = None,
                        channel_id: int = None, operator_id: int = None):
        return self.post(
            url=URL('v1/messages'),
            data=non_empty_dict(client_id=client_id, text=text, transport=transport, attachment=attachment,
                                pdf=pdf, type=message_type, channel_id=channel_id, operator_id=operator_id)
        )

    def _post__messages_inbox(self, channel_id: int = None, body: str = None, image: str = None, video: str = None,
                              location: Coordinates = None, from_client: Sender = None):
        return self.post(
            url=URL('v1/messages/inbox'),
            data=non_empty_dict(channel_id=channel_id, body=body, image=image, video=video, location=location,
                                from_client=from_client)
        )

    def _post__messages_assign(self, message_id: int, operator_id: int):
        return self.post(
            url=URL(f'v1/messages/{message_id}/assign'),
            data=non_empty_dict(operator_id=operator_id)
        )

    def _get__clients(self, limit: int = None, offset: int = None):
        return self.get(
            url=URL(f'v1/clients'),
            params=non_empty_dict(limit=limit, offset=offset)
        )

    def _get__client(self, client_id: int, extra: str = '', **kwargs):
        return self.get(
            url=URL(f'v1/clients/{client_id}' + f'/{extra}' if extra else ''),
            **kwargs
        )

    def _get__client_transport(self, client_id: int):
        return self._get__client(client_id=client_id, extra='transport')

    def _get__client_last_question(self, client_id: int):
        return self._get__client(client_id=client_id, extra='last_question')

    def _get__client_dialogs(self, client_id: int, limit: int = None, offset: int = None):
        return self._get__client(client_id=client_id, extra='dialogs',
                                 params=non_empty_dict(limit=limit, offset=offset))

    def _get__client_by_phone(self, phone: str):
        return self.get(
            url=URL(f'v1/clients'),
            params=non_empty_dict(phone=phone)
        )

    def _get__clients_by_tags(self, tags: List[str], limit: int = None, offset: int = None):
        return self.get(
            url=URL(f'v1/clients'),
            params=non_empty_dict(
                tags=','.join(tags) if tags else '',
                limit=limit,
                offset=offset
            )
        )

    def _post__clients(self, phone: str, transport: Transport, channel_id: int):
        return self.post(
            url=URL('v1/clients'),
            params=non_empty_dict(phone=phone, transport=transport, channel_id=channel_id)
        )

    def _put__client(self, client_id: int, nickname: str = None, comment: str = None, extra_comment_1: str = None,
                     extra_comment_2: str = None, extra_comment_3: str = None):
        return self.put(
            url=URL(f'v1/clients/{client_id}'),
            data=non_empty_dict(nickname=nickname, comment=comment, extra_comment_1=extra_comment_1,
                                extra_comment_2=extra_comment_2, extra_comment_3=extra_comment_3)
        )

    def _get__operators(self, phone: str = None, email: str = None, online: bool = None, limit: int = None,
                        offset: int = None):
        return self.get(
            url=URL('v1/operators'),
            params=non_empty_dict(phone=phone, email=email, online=online, limit=limit, offset=offset)
        )

    def _get__dialogs(self, dialog_id: int = None, operator_id: int = None, state: DialogState = None,
                      limit: int = None, offset: int = None):
        return self.get(
            url=URL('v1/dialogs' + f'/{dialog_id}' if dialog_id else ''),
            params=non_empty_dict(operator_id=operator_id, state=state, limit=limit, offset=offset)
        )

    def _get__unanswered_dialogs(self, seconds_to_overdue: int = 600):
        return self.get(
            url=URL('v1/dialogs/unanswered'),
            params=non_empty_dict(limit=seconds_to_overdue)
        )

    def _put__dialog(self, dialog_id: int, operator_id: int = None, state: DialogState = None):
        return self.put(
            url=URL(f'v1/dialogs/{dialog_id}'),
            data=non_empty_dict(operator_id=operator_id, state=state)
        )

    def _get__tags(self, tag_id: int = None, limit: int = None, offset: int = None):
        return self.get(
            url=URL('v1/tags' + f'/{tag_id}' if tag_id else ''),
            params=non_empty_dict(limit=limit, offset=offset)
        )

    def _post__assign_tags_to_client(self, tag_ids: List[int], client_id: int):
        return self.post(
            url=URL('v1/tags/assign_to'),
            data=non_empty_dict(tag_ids=tag_ids, assignee_type='client', assignee_id=client_id)
        )

    def _delete__tags_from_client(self, tag_id: int, client_id: int):
        return self.post(
            url=URL(f'v1/tags/{tag_id}/delete_from'),
            data=non_empty_dict(client_id=client_id)
        )

    def _get__templates(self, template_id: int = None, limit: int = None, offset: int = None):
        return self.get(
            url=URL('v1/templates' + f'/{template_id}' if template_id else ''),
            params=non_empty_dict(limit=limit, offset=offset)
        )

    def _post__qr_decode(self, image_url: str):
        return self.post(
            url=URL('v1/qr-decode'),
            data=non_empty_dict(image_path=image_url)
        )

    def _get__roles(self):
        return self.get(url=URL('v1/help/roles'))

    def _get__dialog_states(self):
        return self.get(url=URL('v1/help/dialog_states'))

    def _get__channels(self, phone: str = None, limit: int = None, offset: int = None):
        return self.get(url=URL('v1/channels'), params=non_empty_dict(phone=phone, limit=limit, offset=offset))

    def _get__regions(self):
        return self.get(url=URL('v1/regions'))

    def _get__countries(self):
        return self.get(url=URL('v1/countries'))

    def _get__transports(self):
        return self.get(url=URL('v1/help/transports'))

    def _get__messages_read(self, message_id: int, is_read: bool):
        return self.get(url=URL(f'v1/messages/{message_id}/' + 'read' if is_read else 'unread'))

    def _get__api_info(self):
        return self.get(url=URL('v1/companies/api_info'))

    def _get__api_modes(self):
        return self.get(url=URL('v1/help/api_modes'))
