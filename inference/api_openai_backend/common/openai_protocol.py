from typing import Any, Dict, Literal, List, TypeVar, Optional, Set, Tuple, Type, Union

from pydantic import BaseModel, Field, root_validator, validator
from enum import IntEnum, Enum
import uuid
import time
import yaml

TModel = TypeVar("TModel", bound="ModelList")
TCompletion = TypeVar("TCompletion", bound="CompletionResponse")
TChatCompletion = TypeVar("TChatCompletion", bound="ChatCompletion")
ModelT = TypeVar("ModelT", bound=BaseModel)

class QueuePriority(IntEnum):
    """Lower value = higher priority"""

    GENERATE_TEXT = 0
    BATCH_GENERATE_TEXT = 1

class ErrorResponse(BaseModel):
    object: str = "error"
    message: str
    internal_message: str
    type: str
    param: Dict[str, Any] = {}
    code: int


class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "llmonray"
    root: Optional[str] = None
    parent: Optional[str] = None
    permission: List[str]       # todo: not aligned


class ModelList(BaseModel):
    object: str = "list"
    data: List[ModelCard] = []


class UsageInfo(BaseModel):
    prompt_tokens: int
    total_tokens: int
    completion_tokens: Optional[int] = 0

    @classmethod
    def from_response(
        cls, response: Union["ModelResponse", Dict[str, Any]]
    ) -> "UsageInfo":
        if isinstance(response, BaseModel):
            response_dict = response.dict()
        else:
            response_dict = response
        return cls(
            prompt_tokens=response_dict["num_input_tokens"] or 0,
            completion_tokens=response_dict["num_generated_tokens"] or 0,
            total_tokens=(response_dict["num_input_tokens"] or 0)
            + (response_dict["num_generated_tokens"] or 0),
        )


class CompletionResponseChoice(BaseModel):
    index: int
    text: str
    logprobs: Optional[int] = None
    finish_reason: Optional[str]


class CompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{str(uuid.uuid4().hex)}")
    object: str = "text_completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[CompletionResponseChoice]
    usage: Optional[UsageInfo]


class ChatMessage(BaseModel):
    role: Literal["system", "assistant", "user"]
    content: str

    def __str__(self):
        return self.content


class DeltaRole(BaseModel):
    role: Literal["system", "assistant", "user"]

    def __str__(self):
        return self.role


class DeltaContent(BaseModel):
    content: str

    def __str__(self):
        return self.content


class DeltaEOS(BaseModel):
    class Config:
        extra = "forbid"


class MessageChoices(BaseModel):
    message: ChatMessage
    index: int
    finish_reason: Optional[str]


class DeltaChoices(BaseModel):
    delta: Union[DeltaRole, DeltaContent, DeltaEOS]
    index: int
    finish_reason: Optional[str]


class ChatCompletion(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[Union[MessageChoices, DeltaChoices]]
    usage: Optional[UsageInfo]


class Prompt(BaseModel):
    prompt: Union[str, List[ChatMessage]]
    use_prompt_format: bool = True
    parameters: Optional[Union[Dict[str, Any], BaseModel]] = None


class PromptFormat(BaseModel):
    system: str
    assistant: str
    trailing_assistant: str
    user: str

    default_system_message: str = ""
    system_in_user: bool = False
    add_system_tags_even_if_message_is_empty: bool = False
    strip_whitespace: bool = True

    @validator("system")
    def check_system(cls, value):
        assert value and (
            "{instruction}" in value
        ), "system must be a string containing '{instruction}'"
        return value

    @validator("assistant")
    def check_assistant(cls, value):
        assert (
            value and "{instruction}" in value
        ), "assistant must be a string containing '{instruction}'"
        return value

    @validator("user")
    def check_user(cls, value):
        assert value and (
            "{instruction}" in value
        ), "user must be a string containing '{instruction}'"
        return value

    @root_validator(skip_on_failure=True)
    def check_user_system_in_user(cls, values):
        if values["system_in_user"]:
            assert (
                "{system}" in values["user"]
            ), "If system_in_user=True, user must contain '{system}'"
        return values

    def generate_prompt(self, messages: Union[Prompt, List[ChatMessage]]) -> str:
        if isinstance(messages, Prompt):
            if isinstance(messages.prompt, str):
                if not messages.use_prompt_format:
                    return messages.prompt
                new_messages = []
                if self.default_system_message:
                    new_messages.append(
                        ChatMessage(role="system", content=self.default_system_message),
                    )
                new_messages.append(
                    ChatMessage(role="user", content=messages.prompt),
                )
                messages = new_messages
            else:
                messages = messages.prompt

        # Get system message
        system_message_index = -1
        for i, message in enumerate(messages):
            if message.role == "system":
                if system_message_index == -1:
                    system_message_index = i
                else:
                    raise ValueError("Only one system message can be specified.")

        system_message = None
        if system_message_index != -1:
            system_message = messages.pop(system_message_index)
        elif (
            self.default_system_message or self.add_system_tags_even_if_message_is_empty
        ):
            system_message = ChatMessage(role="system", content=self.default_system_message)
        if (
            system_message is not None
            and (
                system_message.content or self.add_system_tags_even_if_message_is_empty
            )
            and not self.system_in_user
        ):
            messages.insert(0, system_message)

        prompt = []
        for message in messages:
            message_content = message.content
            if self.strip_whitespace:
                message_content = message_content.strip()
            if message.role == "system":
                prompt.append(self.system.format(instruction=message_content))
            elif message.role == "user":
                if self.system_in_user:
                    prompt.append(
                        self.user.format(
                            instruction=message_content,
                            system=self.system.format(
                                instruction=system_message.content
                            )
                            if system_message
                            else "",
                        )
                    )
                    system_message = None
                else:
                    prompt.append(self.user.format(instruction=message_content))
            elif message.role == "assistant":
                prompt.append(self.assistant.format(instruction=message_content))
        prompt.append(self.trailing_assistant)
        return "".join(prompt)


class BaseModelExtended(BaseModel):
    @classmethod
    def parse_yaml(cls: Type[ModelT], file, **kwargs) -> ModelT:
        kwargs.setdefault("Loader", yaml.SafeLoader)
        dict_args = yaml.load(file, **kwargs)
        return cls.parse_obj(dict_args)

    def yaml(
        self,
        *,
        stream=None,
        include=None,
        exclude=None,
        by_alias: bool = False,
        skip_defaults: Union[bool, None] = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        **kwargs,
    ):
        """
        Generate a YAML representation of the model, `include` and `exclude` arguments as per `dict()`.
        """
        return yaml.dump(
            self.dict(
                include=include,
                exclude=exclude,
                by_alias=by_alias,
                skip_defaults=skip_defaults,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
            ),
            stream=stream,
            **kwargs,
        )


class ComputedPropertyMixin:
    """
    Include properties in the dict and json representations of the model.
    """

    # Replace with pydantic.computed_field once it's available
    @classmethod
    def get_properties(cls):
        return [prop for prop in dir(cls) if isinstance(getattr(cls, prop), property)]

    def dict(self, *args, **kwargs):
        self.__dict__.update(
            {prop: getattr(self, prop) for prop in self.get_properties()}
        )
        return super().dict(*args, **kwargs)  # type: ignore

    def json(
        self,
        *args,
        **kwargs,
    ) -> str:
        self.__dict__.update(
            {prop: getattr(self, prop) for prop in self.get_properties()}
        )

        return super().json(*args, **kwargs)  # type: ignore


class ModelResponse(ComputedPropertyMixin, BaseModelExtended):
    generated_text: Optional[str] = None
    num_input_tokens: Optional[int] = None
    num_input_tokens_batch: Optional[int] = None
    num_generated_tokens: Optional[int] = None
    num_generated_tokens_batch: Optional[int] = None
    preprocessing_time: Optional[float] = None
    generation_time: Optional[float] = None
    timestamp: Optional[float] = Field(default_factory=time.time)
    finish_reason: Optional[str] = None
    error: Optional[ErrorResponse] = None

    @root_validator(skip_on_failure=True)
    def text_or_error_or_finish_reason(cls, values):
        if (
            values.get("generated_text") is None
            and values.get("error") is None
            and values.get("finish_reason") is None
        ):
            raise ValueError(
                "Either 'generated_text' or 'error' or 'finish_reason' must be set"
            )
        return values

    @classmethod
    def merge_stream(cls, *responses: "ModelResponse") -> "ModelResponse":
        """
        Merge a stream of responses into a single response.

        The generated text is concatenated. Fields are maxed, except for
        num_generated_tokens and generation_time, which are summed.
        """
        if len(responses) == 1:
            return responses[0]

        generated_text = "".join(
            [response.generated_text or "" for response in responses]
        )
        num_input_tokens = [
            response.num_input_tokens
            for response in responses
            if response.num_input_tokens is not None
        ]
        max_num_input_tokens = max(num_input_tokens) if num_input_tokens else None
        num_input_tokens_batch = [
            response.num_input_tokens_batch
            for response in responses
            if response.num_input_tokens_batch is not None
        ]
        max_num_input_tokens_batch = (
            max(num_input_tokens_batch) if num_input_tokens_batch else None
        )
        num_generated_tokens = [
            response.num_generated_tokens
            for response in responses
            if response.num_generated_tokens is not None
        ]
        total_generated_tokens = (
            sum(num_generated_tokens) if num_generated_tokens else None
        )
        num_generated_tokens_batch = [
            response.num_generated_tokens_batch
            for response in responses
            if response.num_generated_tokens_batch is not None
        ]
        total_generated_tokens_batch = (
            sum(num_generated_tokens_batch) if num_generated_tokens_batch else None
        )
        preprocessing_time = [
            response.preprocessing_time
            for response in responses
            if response.preprocessing_time is not None
        ]
        max_preprocessing_time = max(preprocessing_time) if preprocessing_time else None
        generation_time = [
            response.generation_time
            for response in responses
            if response.generation_time is not None
        ]
        total_generation_time = sum(generation_time) if generation_time else None
        error = next(
            (response.error for response in reversed(responses) if response.error), None
        )

        return cls(
            generated_text=generated_text,
            num_input_tokens=max_num_input_tokens,
            num_input_tokens_batch=max_num_input_tokens_batch,
            num_generated_tokens=total_generated_tokens,
            num_generated_tokens_batch=total_generated_tokens_batch,
            preprocessing_time=max_preprocessing_time,
            generation_time=total_generation_time,
            timestamp=responses[-1].timestamp,
            finish_reason=responses[-1].finish_reason,
            error=error,
        )

    @property
    def total_time(self) -> Optional[float]:
        if self.generation_time is None and self.preprocessing_time is None:
            return None
        return (self.preprocessing_time or 0) + (self.generation_time or 0)

    @property
    def num_total_tokens(self) -> Optional[float]:
        try:
            return (self.num_input_tokens or 0) + (self.num_generated_tokens or 0)
        except Exception:
            return None

    @property
    def num_total_tokens_batch(self) -> Optional[float]:
        try:
            return (self.num_input_tokens_batch or 0) + (
                self.num_generated_tokens_batch or 0
            )
        except Exception:
            return None

    def unpack(self) -> Tuple["ModelResponse", ...]:
        return (self,)


class Completions(BaseModel):
    model: str
    prompt: str
    suffix: Optional[str] = None
    stream: bool = False
    echo: Optional[bool] = False
    user: Optional[str] = None
    max_tokens: Optional[int] = 16
    top_k: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: int = 1
    logprobs: Optional[int] = None
    logit_bias: Optional[Dict[str, float]] = None
    stop: Optional[List[str]] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    best_of: int = 1


class ChatCompletions(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: bool = False
    echo: Optional[bool] = False
    user: Optional[str] = None
    top_k: Optional[int] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: int = 1
    logprobs: Optional[int] = None
    logit_bias: Optional[Dict[str, float]] = None
    stop: Optional[List[str]] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    best_of: int = 1
    _ignored_fields: Set[str] = set()


class FinishReason(str, Enum):
    LENGTH = "length"
    STOP = "stop"
    ERROR = "error"
    CANCELLED = "cancelled"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_vllm_finish_reason(
        cls, finish_reason: Optional[str]
    ) -> Optional["FinishReason"]:
        if finish_reason is None:
            return None
        if finish_reason == "stop":
            return cls.STOP
        if finish_reason == "length":
            return cls.LENGTH
        if finish_reason == "abort":
            return cls.CANCELLED
        return cls.STOP