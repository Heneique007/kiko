from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from fastapi import HTTPException
from .config import limits
from .files import store
from .prompts import load_prompt


class Message(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    role: Literal['user', 'assistant']
    content: str = Field(default='', max_length=160000)
    file_ids: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def valid(self):
        if self.role == 'assistant' and self.file_ids:
            raise ValueError('Só mensagens do utilizador podem conter anexos.')
        if not self.content.strip() and not self.file_ids:
            raise ValueError('Mensagem vazia.')
        if len(set(self.file_ids)) != len(self.file_ids) or any(not fid.startswith('file-') or len(fid) > 100 for fid in self.file_ids):
            raise ValueError('Identificadores de anexos inválidos.')
        return self


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    mode: Literal['learn', 'think', 'quick']
    messages: list[Message] = Field(min_length=1, max_length=200)
    stream: bool = True

    @model_validator(mode='after')
    def valid(self):
        if self.messages[0].role != 'user' or self.messages[-1].role != 'user':
            raise ValueError('A conversa deve começar e terminar com uma mensagem do utilizador.')
        for i, message in enumerate(self.messages):
            if i and message.role == self.messages[i-1].role:
                raise ValueError('As mensagens devem alternar entre utilizador e assistente.')
        return self


async def prepare_messages(data, uid):
    settings = limits()
    if sum(len(m.content) for m in data.messages) > settings['max_context_chars']:
        raise HTTPException(422, 'Conversa demasiado longa. Inicie uma nova conversa.')
    prompt = load_prompt(data.mode)
    result = [{'role': 'system', 'content': prompt}]
    total = 0
    attachment_count = 0
    for m in data.messages:
        if len(m.file_ids) > settings['max_attachments']:
            raise HTTPException(422, 'Demasiados anexos na mensagem.')
        attachment_count += len(m.file_ids)
        if attachment_count > settings['max_context_attachments']:
            raise HTTPException(422, 'Demasiados anexos no contexto. Inicie uma nova conversa.')
        content = m.content
        total += len(content)
        if m.file_ids:
            parts = [{'type': 'text', 'text': content or 'Analise os anexos.'}]
            for fid in m.file_ids:
                part = await store.part(uid, fid)
                if part['type'] == 'text':
                    total += len(part['text'])
                parts.append(part)
            content = parts
        if total > settings['max_context_chars']:
            raise HTTPException(422, 'O texto e os anexos excedem o limite de contexto. Inicie uma nova conversa com menos conteúdo.')
        result.append({'role': m.role, 'content': content})
    return result
