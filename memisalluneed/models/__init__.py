from memisalluneed.models.base import ChatMessage, ChatModel

__all__ = ["ChatMessage", "ChatModel", "OpenAICompatibleChatModel"]


def __getattr__(name: str):
    if name == "OpenAICompatibleChatModel":
        from memisalluneed.models.openai_compatible import OpenAICompatibleChatModel

        return OpenAICompatibleChatModel
    raise AttributeError(name)
