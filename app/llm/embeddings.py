from sentence_transformers import SentenceTransformer
from typing import Protocol 
from numpy import ndarray
import asyncio


class EmbeddingService(Protocol):

    @property
    def model_name(self) -> str:
        pass

    @property
    def dimensions(self) -> int:
        pass

    async def embed_query(
            self,
            *,
            text: str,
    ) -> tuple[float,...]:
        pass

    async def embed_document(
            self,
            *,
            text: str,
    ) -> tuple[float,...]:
        pass

class TextEmbeddingService:
    def __init__(
            self,
            *,
            model_name: str = "intfloat/multilingual-e5-small",
    ) -> None:
        self._model_name = model_name
        self._model = SentenceTransformer(self._model_name)
        _dimensions = self._model.get_embedding_dimension()
        if _dimensions != 384:
            raise ValueError(f"Different or missing embedding dimensions, should be 384, but is: {_dimensions }, for model: {model_name}")
        
        self._dimensions = _dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_query(self,*, text: str) -> tuple[float,...]:
        query = f"query: {text}"
        embeddings =  await asyncio.to_thread(self._model.encode_query, query, normalize_embeddings = True)
        self.validate_dimensions(embeddings=embeddings)
        result = tuple(float(e) for e in embeddings)
        return result

    async def embed_document(self,*, text:str) -> tuple[float,...]:
        document = f"passage: {text}"
        embeddings_d = await asyncio.to_thread(self._model.encode_document, document, normalize_embeddings=True)
        self.validate_dimensions(embeddings=embeddings_d)
        result = tuple(float(e) for e in embeddings_d)
        return result
        

    def validate_dimensions(self, embeddings: ndarray) -> None:
        if len(embeddings) != self._dimensions:
            raise ValueError("Encoding: Embeddings not valid!")


        





