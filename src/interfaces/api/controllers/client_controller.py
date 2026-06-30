"""HTTP controller for client onboarding resources.

Thin layer: validate input -> call use case -> serialize output.
Business rules are never evaluated here.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.dto.client_dto import AddDocumentDTO, CreateClientDTO
from src.application.exceptions import ClientNotFoundError, InvalidClientRequestError
from src.application.use_cases.add_client_document import AddClientDocumentUseCase
from src.application.use_cases.get_client import GetClientUseCase
from src.application.use_cases.list_clients import ListClientsUseCase
from src.application.use_cases.onboard_client import OnboardClientUseCase
from src.interfaces.api.dependencies import (
    get_add_document_use_case,
    get_get_client_use_case,
    get_list_clients_use_case,
    get_onboard_client_use_case,
)
from src.interfaces.api.schemas import AddDocumentRequest, ClientResponse, CreateClientRequest

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def onboard_client(
    payload: CreateClientRequest,
    use_case: OnboardClientUseCase = Depends(get_onboard_client_use_case),
) -> ClientResponse:
    try:
        result = use_case.execute(
            CreateClientDTO(
                full_name=payload.full_name, email=payload.email, tax_id=payload.tax_id
            )
        )
    except InvalidClientRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ClientResponse(**result.__dict__)


@router.get("", response_model=List[ClientResponse])
def list_clients(
    use_case: ListClientsUseCase = Depends(get_list_clients_use_case),
) -> List[ClientResponse]:
    results = use_case.execute()
    return [ClientResponse(**result.__dict__) for result in results]


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: str,
    use_case: GetClientUseCase = Depends(get_get_client_use_case),
) -> ClientResponse:
    try:
        result = use_case.execute(client_id)
    except ClientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ClientResponse(**result.__dict__)


@router.post("/{client_id}/documents", response_model=ClientResponse)
def add_document(
    client_id: str,
    payload: AddDocumentRequest,
    use_case: AddClientDocumentUseCase = Depends(get_add_document_use_case),
) -> ClientResponse:
    try:
        result = use_case.execute(
            AddDocumentDTO(client_id=client_id, document_name=payload.document_name)
        )
    except ClientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ClientResponse(**result.__dict__)
