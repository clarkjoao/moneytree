from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.transaction import Classificacao, Transaction
from transaction_store import load_month_transactions, save_classificacao_snapshot, load_overlay_by_id, merge_classificacao
from classifier.rule_engine import append_exact_rule

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]
PROCESSED_ROOT = ROOT / "data" / "processed"
CONFIG_ROOT = ROOT / "config"

class ReviewPayload(BaseModel):
    mes: str
    classificacao: dict

@router.patch("/transactions/{transaction_id}")
def update_transaction(transaction_id: str, payload: ReviewPayload):
    mes = payload.mes
    updates = payload.classificacao
    
    month_dir = PROCESSED_ROOT / mes
    transactions = load_month_transactions(PROCESSED_ROOT, mes)
    
    target_tx = None
    for tx in transactions:
        if tx.id == transaction_id:
            target_tx = tx
            break
            
    if not target_tx:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
        
    # Apply updates
    prior = target_tx.classificacao.model_dump()
    merged = {**prior, **updates}
    new_classificacao = Classificacao(**merged)
    target_tx.classificacao = new_classificacao
    
    # Save snapshot
    overlay = load_overlay_by_id(month_dir, mes)
    overlay[transaction_id] = new_classificacao.model_dump(mode="json")
    
    # Re-save with proper merging for persistence
    # We must patch the original transactions and save the full list or we can just run save_classificacao_snapshot
    # which builds by_id. So we just update the transaction object and save the list
    save_classificacao_snapshot(month_dir, mes, transactions)
    
    # Check if confidence is 1.0 to append exact rule
    if new_classificacao.confianca == 1.0:
        append_exact_rule(
            CONFIG_ROOT / "regras.json", 
            target_tx.descricao_original, 
            new_classificacao
        )
        
    return {"status": "success", "transaction_id": transaction_id}
