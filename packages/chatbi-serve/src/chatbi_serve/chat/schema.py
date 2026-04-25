from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class ImageUrlPart(BaseModel):
    url: str


class FileUrlPart(BaseModel):
    url: str
    file_name: str


class ContentPart(BaseModel):
    type: Literal["text", "image_url", "file_url"]
    text: Optional[str] = None
    image_url: Optional[ImageUrlPart] = None
    file_url: Optional[FileUrlPart] = None


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, List[ContentPart]]


class ModelConfig(BaseModel):
    model_name: str
    base_url: str
    api_key: str
    model_type: str = "openai"


class ChatRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    model_config_field: Optional[ModelConfig] = Field(None, alias="model_config")
    select_param: Optional[str] = None
    ext_info: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None

    class Config:
        populate_by_name = True


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: Optional[Dict[str, Any]] = None
